"""
测试协程ID日志打印功能
"""
import asyncio
from utils.logger import logger


async def task_1():
    """测试任务1"""
    logger.info("Task 1 开始执行")
    await asyncio.sleep(0.1)
    logger.info("Task 1 执行中")
    await asyncio.sleep(0.1)
    logger.info("Task 1 执行完成")


async def task_2():
    """测试任务2"""
    logger.warning("Task 2 开始执行")
    await asyncio.sleep(0.15)
    logger.warning("Task 2 执行中")
    await asyncio.sleep(0.15)
    logger.warning("Task 2 执行完成")


async def task_3():
    """测试任务3"""
    logger.error("Task 3 开始执行")
    await asyncio.sleep(0.05)
    logger.error("Task 3 执行中")
    await asyncio.sleep(0.05)
    logger.error("Task 3 执行完成")


async def main():
    """主函数：并发运行多个任务"""
    logger.info("开始测试协程ID日志功能")
    
    # 创建并发任务
    tasks = [
        asyncio.create_task(task_1(), name="TaskA"),
        asyncio.create_task(task_2(), name="TaskB"),
        asyncio.create_task(task_3(), name="TaskC"),
    ]
    
    # 等待所有任务完成
    await asyncio.gather(*tasks)
    
    logger.info("协程ID日志测试完成")


if __name__ == "__main__":
    # 主线程日志测试
    logger.info("主线程开始")
    
    # 运行异步任务
    asyncio.run(main())
    
    # 主线程结束
    logger.info("主线程结束")
