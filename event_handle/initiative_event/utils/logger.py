"""
统一日志配置模块 - 基于 Structlog + ContextVars

提供全局日志配置，支持：
- 结构化日志输出（JSON 格式）
- 基于 ContextVars 的请求上下文追踪
- 自动记录 request_id、user_id、group_id 等信息
- 协程安全的上下文传递
"""
import logging
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from contextvars import ContextVar
from typing import Any, Dict, Optional

import structlog
from structlog.types import EventDict, Processor

from const import LOG_LEVEL, LOG_FILE, BASE_DIR

# ==================== ContextVars 定义 ====================
# 用于在整个请求生命周期中传递上下文信息
# 只保留 request_id，因为它在整个请求生命周期中是唯一且不变的
# 其他业务字段（event_type, group_id 等）应该在记录日志时动态传递
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


# ==================== Structlog 处理器 ====================
def add_context_from_contextvars(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    从 ContextVars 中提取请求 ID 并添加到日志事件中
    
    只注入 request_id，其他业务字段（event_type, group_id 等）
    应该在调用 logger 时作为参数传递，以支持同一请求中的动态变化。
    """
    request_id = request_id_ctx.get()
    if request_id:
        event_dict["request_id"] = request_id
    
    return event_dict


def drop_color_message_key(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    删除 structlog 内部使用的 color_message 键
    避免在最终输出中出现重复信息
    """
    event_dict.pop("color_message", None)
    return event_dict


# ==================== 日志配置函数 ====================
def setup_structlog() -> structlog.BoundLogger:
    """
    配置并返回 structlog 日志实例
    
    配置策略：
    - 使用 JSON 格式输出到文件（便于日志分析系统解析）
    - 使用彩色格式输出到控制台（便于开发调试）
    - 自动添加时间戳、日志级别、调用位置等信息
    - 通过 ContextVars 自动注入请求上下文
    
    Returns:
        structlog.BoundLogger: 配置好的结构化日志实例
    """
    # 获取日志级别
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    
    # 配置标准 logging 模块（作为 structlog 的后端）
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    
    # 配置文件处理器（JSON 格式）
    if not os.path.exists(f"{BASE_DIR}/logs"):
        os.makedirs(f"{BASE_DIR}/logs")
    struct_log_file = f"logs/struct_{LOG_FILE}"
    file_handler = logging.FileHandler(struct_log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    
    # 为文件输出配置 JSON 格式
    file_handler.setFormatter(
        logging.Formatter("%(message)s")
    )
    
    # 额外配置一个纯文本文件处理器，适配只支持字符串日志的采集工具
    text_file_handler = logging.FileHandler(f"logs/{LOG_FILE}", encoding="utf-8")
    text_file_handler.setLevel(log_level)
    
    # 获取根日志记录器并添加文件处理器
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(text_file_handler)
    
    # 配置 structlog 处理器链
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,  # 合并 contextvars
        structlog.stdlib.add_log_level,  # 添加日志级别
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S,%f", utc=False),  # 生成 datetime 对象时间戳
        structlog.processors.StackInfoRenderer(),  # 渲染栈信息
        add_context_from_contextvars,  # 从 ContextVars 添加上下文
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),  # 添加调用位置信息
    ]
    
    # 配置 structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # 配置标准库 logging 的格式化器
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),  # JSON 格式输出
        ],
    )
    
    # 为控制台输出配置彩色格式
    console_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            drop_color_message_key,
            structlog.dev.ConsoleRenderer(
                colors=True,
                pad_event=0,
                pad_level=False
            ),  # 彩色控制台输出，无填充
        ],
    )
    
    # 为纯文本文件输出配置格式（便于未适配 JSON 的日志采集工具）
    text_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            drop_color_message_key,
            structlog.dev.ConsoleRenderer(
                colors=False,
                pad_event=0,
                pad_level=False
            ),
        ],
    )
    
    # 应用格式化器
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            handler.setFormatter(console_formatter)
        elif handler is file_handler:
            handler.setFormatter(formatter)
        elif handler is text_file_handler:
            handler.setFormatter(text_formatter)
        else:
            handler.setFormatter(formatter)
    
    return structlog.get_logger()


# ==================== 上下文管理工具函数 ====================
def set_request_context(request_id: Optional[str] = None) -> str:
    """
    设置请求上下文信息
    
    在请求处理开始时调用，生成并存储唯一的 request_id。
    其他业务字段（event_type, group_id 等）应该在记录日志时动态传递。
    
    Args:
        request_id: 请求唯一标识（如果不提供则自动生成 UUID）
    
    Returns:
        str: 请求ID
    
    Example:
        # 设置请求上下文
        request_id = set_request_context()
        
        # 记录日志时传递业务字段
        logger.info(
            "处理请求",
            event_type="greet",
            group_id="group_123",
            user_name="Alice"
        )
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    
    request_id_ctx.set(request_id)
    
    return request_id


def clear_request_context():
    """
    清除请求上下文信息
    
    在请求处理结束时调用，避免 request_id 泄漏到其他请求。
    """
    request_id_ctx.set(None)


def get_current_request_id() -> Optional[str]:
    """获取当前请求ID"""
    return request_id_ctx.get()


# ==================== 全局日志实例 ====================
logger = setup_structlog()
