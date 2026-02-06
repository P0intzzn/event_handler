import logging
import asyncio


class AsyncioFilter(logging.Filter):
    """为日志记录添加协程ID"""
    def filter(self, record):
        try:
            # 获取当前协程的任务对象
            task = asyncio.current_task()
            if task:
                # 使用任务名称或ID
                record.coroutine_id = f"{task.get_name()}_{id(task) % 10000:04d}"
            else:
                record.coroutine_id = "main"
        except RuntimeError:
            # 没有运行中的事件循环
            record.coroutine_id = "no_loop"
        return True


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(coroutine_id)s] %(filename)s:%(lineno)d %(funcName)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
        logging.FileHandler('event_handler.log', encoding='utf-8')  # 输出到文件
    ]
)

logger = logging.getLogger(__name__)
# 为logger添加协程ID过滤器
asyncio_filter = AsyncioFilter()
logger.addFilter(asyncio_filter)

# 为所有handlers添加过滤器
for handler in logging.root.handlers:
    handler.addFilter(asyncio_filter)