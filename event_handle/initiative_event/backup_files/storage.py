import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from statistics import mean
from typing import List, Dict

import asyncmy
import redis.asyncio as redis
import json
from asyncmy.cursors import DictCursor
from dotenv import load_dotenv

from logger import logger

dao = None
_dao_lock = None  # 异步锁，用于保证初始化的线程安全和异步安全

class ChatStorageHelper:
    """
    获取上下文调用方式：
    实例化此类
        user_context = await self.storage.get_user_context(self.group_id, user_id)
        return self.storage.user_context_list_to_str(user_context)
    聊天上下文存储辅助类（使用 dict_storage 的 Redis 连接）
    """

    @staticmethod
    async def get_group_context(run_id: str) -> List[Dict]:
        """获取群聊上下文"""
        try:
            value = await dao.redis.get(f"group_context:{run_id}")
            logger.info(f"✅ 获取上下文 {run_id}: {value}")
            if value:
                if isinstance(value, bytes):
                    value = value.decode()
                return json.loads(value)
            return []
        except Exception as e:
            logger.error(f"❌ 获取上下文失败: {e}")
            return []

    @staticmethod
    async def get_user_context(run_id: str, user_id: str) -> List[Dict]:
        """获取用户上下文"""
        try:
            value = await dao.redis.get(f"user_context:{run_id}:{user_id}")
            if value:
                if isinstance(value, bytes):
                    value = value.decode()
                return json.loads(value)
            return []
        except Exception as e:
            logger.error(f"❌ 获取用户上下文失败: {e}")
            return []

    # 新增获取所有群聊上下文
    @staticmethod
    async def get_group_context_all(run_id: str) -> List[Dict]:
        """获取所有群聊上下文"""
        try:
            value = await dao.redis.get(f"group_context_all:{run_id}")
            if value:
                if isinstance(value, bytes):
                    value = value.decode()
                return json.loads(value)
            return []
        except Exception as e:
            logger.error(f"❌ 获取所有群聊上下文失败: {e}")
            return []

    @staticmethod
    def context_list_to_str(context: List[Dict]) -> str:
        result = []
        for msg in context:
            if isinstance(msg, dict):
                name = msg.get("name", "unknown")
                content = msg.get("content", "")
                result.append(f"{name}: {content}")
            else:
                result.append(str(msg))
        return "\n".join(result)

    @staticmethod
    def user_context_list_to_str(context: List[Dict]) -> str:
        """将用户消息列表转换为字符串格式（带方括号）"""
        result = []
        for msg in context:
            if isinstance(msg, dict):
                name = msg.get("name", "unknown")
                content = msg.get("content", "")
                result.append(f"[{name}] {content}")
            else:
                result.append(str(msg))
        return "\n".join(result).strip()  # 添加 .strip()


class AsyncMessageMemoryDAO:
    def __init__(self, mysql_cfg=None):
        """
        初始化异步连接池（MySQL + Redis）
        """
        load_dotenv(Path(__file__).parent / ".env")
        self.redis = None
        self._redis_lock = asyncio.Lock()  # Redis 操作锁
        self._initialized = False  # 标记是否已初始化
        self.redis_cfg = {
            "host": os.getenv("REDIS_HOST") or "localhost",
            "port": int(os.getenv("REDIS_PORT") or 6379),
            "db": int(os.getenv("REDIS_DB") or 0),
            "password": os.getenv("REDIS_PASSWORD") or None  # 新增密码字段
        }
        self.storage = ChatStorageHelper()

    # ---------- 初始化 ----------
    async def init_pools(self):
        """初始化 Redis 连接池（带锁保护，避免重复初始化）"""
        async with self._redis_lock:
            # 双重检查：如果已经初始化且连接有效，直接返回
            if self._initialized and self.redis:
                try:
                    await self.redis.ping()
                    logger.debug("✅ Redis 连接已存在且有效，跳过初始化")
                    return
                except Exception as e:
                    logger.warning(f"⚠️ Redis 连接失效，重新初始化: {e}")
                    self._initialized = False
            
            try:
                if not self.redis or not self._initialized:
                    redis_url = f"redis://{self.redis_cfg['host']}:{self.redis_cfg['port']}/{self.redis_cfg['db']}"
                    if self.redis_cfg['password']:
                        redis_url = f"redis://:{self.redis_cfg['password']}@{self.redis_cfg['host']}:{self.redis_cfg['port']}/{self.redis_cfg['db']}"

                    logger.info(f"🔄 Redis cache connection URL: {redis_url}")
                    self.redis = await redis.from_url(
                        redis_url,
                        encoding="utf-8",
                        decode_responses=True,
                    )
                    try:
                        await self.redis.ping()
                        self._initialized = True
                        logger.info("✅ Redis cache connection established")
                    except Exception as e:
                        logger.error(f"❌ Redis连接失败: {e}")
                        self.redis = None
                        self._initialized = False
                        raise e
            except Exception as e:
                logger.error(f"❌ Initialization failed: {e}")
                raise e

    # 标记 message 已被撤回
    async def mark_deleted(self, message_id: str):
        await self.redis.set(f"deleted:{message_id}", "1", ex=60)  # 防止占空间，可设置过期

    # 查询 message 是否被撤回
    async def is_deleted(self, message_id: str) -> bool:
        return await self.redis.exists(f"deleted:{message_id}") == 1

    async def set_flag(self, key, value):
        """设置 Redis 中的标志位"""
        try:
            await self.redis.set(key, value, 180)
        #  logger.info(f"✅ 标志位 '{key}' 设置为: {value}")
        except Exception as e:
            logger.error(f"⚠️ 设置标志位时发生错误: {e}")

    async def get_flag(self, key):
        """读取 Redis 中的标志位"""
        try:
            value = await self.redis.get(key)
            if value:
                pass
            else:
                pass
                #logger.info(f"❌ 标志位 '{key}' 不存在  或是调用ask agnes发生在了判断完成之前")
            return "init"
        except Exception as e:
            logger.error(f"⚠️ 读取标志位时发生错误: {e}")
            return None

    async def close_redis(self):
        """关闭 Redis 连接（带锁保护）"""
        async with self._redis_lock:
            if self.redis:
                try:
                    await self.redis.close()
                    self.redis = None
                    self._initialized = False
                    logger.info("✅ Redis connection pool closed.")
                except Exception as e:
                    logger.error(f"⚠️ 关闭 Redis 连接时出错: {e}")
    
    async def ensure_redis_connection(self):
        """确保 Redis 连接可用（健康检查）"""
        if not self._initialized or not self.redis:
            await self.init_pools()
        else:
            try:
                await self.redis.ping()
            except Exception as e:
                logger.warning(f"⚠️ Redis ping 失败，重新初始化: {e}")
                await self.init_pools()

# ✅ 在模块加载时就初始化连接池（异步安全 + 线程安全）
async def init_dao():
    """初始化全局 DAO 实例（单例模式 + 异步锁）"""
    global dao, _dao_lock
    
    # 初始化全局锁
    if _dao_lock is None:
        _dao_lock = asyncio.Lock()
    
    # 使用异步锁确保只初始化一次
    async with _dao_lock:
        if dao is None:
            logger.info("🔄 开始初始化全局 DAO 实例...")
            dao = AsyncMessageMemoryDAO()
            await dao.init_pools()
            logger.info("✅ 全局 DAO 实例初始化完成")
        else:
            # 确保连接有效
            await dao.ensure_redis_connection()
            logger.debug("✅ DAO 实例已存在，确认连接有效")
    
    return dao


async def get_dao():
    """获取 DAO 实例（自动初始化）"""
    global dao
    if dao is None:
        await init_dao()
    else:
        # 确保连接有效
        await dao.ensure_redis_connection()
    return dao


# ✅ 创建全局唯一 DAO 实例
# dao = AsyncMessageMemoryDAO()
