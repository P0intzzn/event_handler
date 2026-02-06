"""
FastAPI 应用主文件

创建应用实例、注册路由、定义生命周期事件
"""
from fastapi import FastAPI
from typing import Optional
from openai import AsyncOpenAI

from app.routers.event import event_handler
from app.routers.interact import interact_handler
from storage.redis_helper import init_dao, dao
from utils.logger import logger
from utils.log_middleware import LogContextMiddleware
from const import (
    APP_TITLE,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    GREET_LLM_MODEL
)

# 创建 FastAPI 应用实例
app = FastAPI(title=APP_TITLE)

# 注册日志上下文中间件（必须最先注册，以便捕获所有请求）
app.add_middleware(LogContextMiddleware)

# 全局 OpenAI 客户端（用于问候语生成服务）
openai_client: Optional[AsyncOpenAI] = None


@app.on_event("startup")
async def startup_event():
    """应用启动事件：初始化 Redis 连接和 OpenAI 客户端"""
    global openai_client
    
    logger.info("应用启动开始", app_title=APP_TITLE)
    
    # 初始化 Redis 连接
    await init_dao()
    logger.info("Redis 连接初始化完成")
    
    # 初始化 OpenAI 客户端
    openai_client = AsyncOpenAI(
        base_url=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY
    )
    logger.info(
        "OpenAI 客户端初始化完成",
        base_url=OPENAI_BASE_URL,
        model=GREET_LLM_MODEL,
    )
    
    logger.info("="*50)
    logger.info("应用启动完成", app_title=APP_TITLE)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件：释放 Redis 连接"""
    logger.info("应用关闭开始", app_title=APP_TITLE)
    
    # 关闭 Redis 连接
    if dao is not None:
        await dao.close_redis()
        logger.info("Redis 连接已关闭")
    
    logger.info("="*50)
    logger.info("应用关闭完成", app_title=APP_TITLE)


# 注册路由
app.include_router(event_handler.router, prefix="/api/initiative", tags=["event"])
app.include_router(interact_handler.router, prefix="/api/initiative", tags=["interaction"])


@app.get("/")
async def root():
    """API 信息页"""
    logger.info("访问API信息页面")
    return {
        "message": "Initiative Event API",
        "version": "1.0",
        "endpoints": {
            "GET /api/initiative/": "API 信息页面"
        }
    }
