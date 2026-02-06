"""
测试 Structlog + ContextVars 日志系统

验证日志上下文管理和协程安全性
"""
import asyncio
import uuid
from utils.logger import (
    logger,
    set_request_context,
    clear_request_context,
    get_current_request_id,
    request_id_ctx,
)


def test_set_and_get_request_context():
    """测试设置和获取请求上下文"""
    request_id = str(uuid.uuid4())
    
    # 设置上下文
    set_request_context(request_id=request_id)
    
    # 验证上下文已设置
    assert get_current_request_id() == request_id
    assert request_id_ctx.get() == request_id
    
    # 记录日志，业务字段作为参数传递
    logger.info(
        "测试日志",
        event_type="greet",
        group_id="test_group_123",
        user_name="test_user",
        extra_field="extra_value",
    )
    
    # 清理上下文
    clear_request_context()
    
    # 验证上下文已清理
    assert get_current_request_id() is None


async def simulate_request(request_num: int, event_type: str):
    """模拟一个请求处理流程"""
    # 设置请求上下文（只设置 request_id）
    request_id = set_request_context()
    
    # 记录日志时传递业务字段
    logger.info(
        f"处理请求开始",
        request_num=request_num,
        event_type=event_type,
        group_id=f"group_{request_num}",
        user_name=f"user_{request_num}",
    )
    
    # 模拟异步操作
    await asyncio.sleep(0.01)
    
    # 在异步操作后，上下文应该仍然保持
    current_request_id = get_current_request_id()
    logger.info(
        f"异步操作完成",
        request_num=request_num,
        event_type=event_type,
        group_id=f"group_{request_num}",
        user_name=f"user_{request_num}",
        context_preserved=(current_request_id == request_id),
    )
    
    # 模拟另一个异步操作
    await asyncio.sleep(0.01)
    
    logger.info(
        f"处理请求结束",
        request_num=request_num,
        event_type=event_type,
        group_id=f"group_{request_num}",
        user_name=f"user_{request_num}",
    )
    
    # 清理上下文
    clear_request_context()
    
    return request_num


async def test_concurrent_requests():
    """测试并发请求的上下文隔离"""
    logger.info("=" * 50)
    logger.info("开始并发请求测试")
    logger.info("=" * 50)
    
    # 创建多个并发请求
    tasks = [
        simulate_request(1, "greet"),
        simulate_request(2, "commentary"),
        simulate_request(3, "greet"),
        simulate_request(4, "commentary"),
        simulate_request(5, "greet"),
    ]
    
    # 并发执行
    results = await asyncio.gather(*tasks)
    
    logger.info("=" * 50)
    logger.info("并发请求测试完成", completed_requests=len(results))
    logger.info("=" * 50)


def test_logger_basic():
    """测试基础日志功能"""
    logger.info("这是一条 INFO 日志")
    logger.warning("这是一条 WARNING 日志", warning_code="W001")
    logger.error("这是一条 ERROR 日志", error_code="E001")
    
    # 测试结构化日志
    logger.info(
        "结构化日志测试",
        user_id=12345,
        action="login",
        ip_address="192.168.1.1",
        metadata={"device": "mobile", "os": "iOS"},
    )


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("测试 1: 基础日志功能")
    print("=" * 60)
    test_logger_basic()
    
    print("\n" + "=" * 60)
    print("测试 2: 请求上下文管理")
    print("=" * 60)
    test_set_and_get_request_context()
    
    print("\n" + "=" * 60)
    print("测试 3: 并发请求上下文隔离（协程安全性）")
    print("=" * 60)
    asyncio.run(test_concurrent_requests())
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)
    print("\n请检查控制台输出和 event_handler.log 文件")
    print("每个请求的所有日志应该都包含相同的 request_id")
    print("不同请求的 request_id 应该是隔离的")
