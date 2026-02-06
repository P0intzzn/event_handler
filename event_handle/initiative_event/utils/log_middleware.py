"""
FastAPI 日志中间件

自动为每个请求注入上下文信息（request_id, event_type, group_id 等）
使得整个请求生命周期内的所有日志都能被追踪关联
"""
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from utils.logger import set_request_context, clear_request_context, logger


class LogContextMiddleware(BaseHTTPMiddleware):
    """
    日志上下文中间件
    
    功能：
    1. 为每个请求生成唯一的 request_id
    2. 将 request_id 注入 ContextVars，使得请求生命周期内的所有日志都包含该标识
    3. 记录请求处理时间
    4. 请求结束后清理上下文，避免内存泄漏
    
    注意：event_type, group_id, user_name 等业务字段不在中间件中设置，
    而是在记录日志时作为参数动态传递，因为它们在请求中可能变化。
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求并注入日志上下文
        
        Args:
            request: FastAPI 请求对象
            call_next: 下一个中间件或路由处理器
        
        Returns:
            Response: 响应对象
        """
        # 生成请求 ID 并设置到 ContextVars
        request_id = str(uuid.uuid4())
        set_request_context(request_id=request_id)
        
        # 记录请求开始
        start_time = time.time()
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
        )
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 记录请求完成
            process_time = time.time() - start_time
            logger.info(
                "Request completed",
                status_code=response.status_code,
                process_time_ms=round(process_time * 1000, 2),
            )
            
            # 在响应头中添加 request_id（方便客户端追踪）
            response.headers["X-Request-ID"] = request_id
            
            return response
        
        except Exception as e:
            # 记录请求失败
            process_time = time.time() - start_time
            logger.error(
                "Request failed",
                error=str(e),
                error_type=type(e).__name__,
                process_time_ms=round(process_time * 1000, 2),
                exc_info=True,
            )
            raise
        
        finally:
            # 清理上下文（重要：避免上下文泄漏到其他请求）
            clear_request_context()
