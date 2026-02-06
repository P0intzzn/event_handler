"""
Redis 连接管理与数据操作模块

提供异步 Redis 操作封装和聊天上下文存储功能
"""
import asyncio
import json
from typing import List, Dict, Optional

import redis.asyncio as redis

from utils.logger import logger
from const import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    REDIS_PASSWORD,
    REDIS_KEY_PREFIX_GROUP,
    REDIS_KEY_PREFIX_USER,
    REDIS_KEY_PREFIX_GROUP_ALL,
    REDIS_KEY_PREFIX_DELETED,
    REDIS_EXPIRE_TIME
)

# 全局 DAO 实例和锁
dao: Optional['AsyncMessageMemoryDAO'] = None
_dao_lock: Optional[asyncio.Lock] = None


class ChatStorageHelper:
    """
    聊天上下文存储辅助类
    
    使用方式:
        user_context = await ChatStorageHelper.get_user_context(group_id, user_id)
        context_str = ChatStorageHelper.user_context_list_to_str(user_context)
    """
    
    @staticmethod
    async def get_group_context(run_id: str) -> List[Dict]:
        """
        获取群聊上下文
        
        Args:
            run_id: 运行 ID（群组 ID）
        
        Returns:
            List[Dict]: 上下文消息列表
        """
        try:
            key = f"{REDIS_KEY_PREFIX_GROUP}{run_id}"
            value = await dao.redis.get(key)
            logger.info(
                "获取群聊上下文成功",
                run_id=run_id,
                value_length=len(value) if value else 0
            )
            if value:
                if isinstance(value, bytes):
                    value = value.decode()
                return json.loads(value)
            return []
        except Exception as e:
            logger.error(
                "获取群聊上下文失败",
                run_id=run_id,
                error=str(e),
                exc_info=True
            )
            return []
    
    @staticmethod
    async def get_user_context(run_id: str, user_id: str) -> List[Dict]:
        """
        获取用户上下文
        
        Args:
            run_id: 运行 ID（群组 ID）
            user_id: 用户 ID
        
        Returns:
            List[Dict]: 用户上下文消息列表
        """
        try:
            key = f"{REDIS_KEY_PREFIX_USER}{run_id}:{user_id}"
            value = await dao.redis.get(key)
            if value:
                if isinstance(value, bytes):
                    value = value.decode()
                return json.loads(value)
            return []
        except Exception as e:
            logger.error(
                "获取用户上下文失败",
                run_id=run_id,
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            return []
    
    @staticmethod
    async def get_group_context_all(run_id: str) -> List[Dict]:
        """
        获取所有群聊上下文
        
        Args:
            run_id: 运行 ID（群组 ID）
        
        Returns:
            List[Dict]: 所有群聊上下文消息列表
        """
        try:
            key = f"{REDIS_KEY_PREFIX_GROUP_ALL}{run_id}"
            value = await dao.redis.get(key)
            if value:
                if isinstance(value, bytes):
                    value = value.decode()
                return json.loads(value)
            return []
        except Exception as e:
            logger.error(
                "获取所有群聊上下文失败",
                run_id=run_id,
                error=str(e),
                exc_info=True
            )
            return []
    
    @staticmethod
    def context_list_to_str(context: List[Dict]) -> str:
        """
        将上下文消息列表转换为字符串格式
        
        Args:
            context: 上下文消息列表
        
        Returns:
            str: 格式化的上下文字符串（name: content）
        """
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
        """
        将用户消息列表转换为字符串格式（带方括号）
        
        Args:
            context: 用户消息列表
        
        Returns:
            str: 格式化的用户上下文字符串（[name] content）
        """
        result = []
        for msg in context:
            if isinstance(msg, dict):
                name = msg.get("name", "unknown")
                content = msg.get("content", "")
                result.append(f"[{name}] {content}")
            else:
                result.append(str(msg))
        return "\n".join(result).strip()


class AsyncMessageMemoryDAO:
    """
    异步消息内存 DAO（Data Access Object）
    
    提供 Redis 连接管理和数据操作功能
    """
    
    def __init__(self):
        """初始化 DAO 实例"""
        self.redis: Optional[redis.Redis] = None
        self._redis_lock = asyncio.Lock()  # Redis 操作锁
        self._initialized = False  # 标记是否已初始化
        self.redis_cfg = {
            "host": REDIS_HOST,
            "port": REDIS_PORT,
            "db": REDIS_DB,
            "password": REDIS_PASSWORD
        }
        self.storage = ChatStorageHelper()
    
    async def init_pools(self):
        """
        初始化 Redis 连接池（带锁保护，避免重复初始化）
        
        Raises:
            Exception: Redis 连接失败
        """
        async with self._redis_lock:
            # 双重检查：如果已经初始化且连接有效，直接返回
            if self._initialized and self.redis:
                try:
                    await self.redis.ping()
                    logger.debug("Redis连接已存在且有效，跳过初始化")
                    return
                except Exception as e:
                    logger.warning(
                        "Redis连接失效，准备重新初始化",
                        error=str(e)
                    )
                    self._initialized = False
            
            try:
                if not self.redis or not self._initialized:
                    # 构建 Redis URL
                    if self.redis_cfg['password']:
                        redis_url = f"redis://:{self.redis_cfg['password']}@{self.redis_cfg['host']}:{self.redis_cfg['port']}/{self.redis_cfg['db']}"
                    else:
                        redis_url = f"redis://{self.redis_cfg['host']}:{self.redis_cfg['port']}/{self.redis_cfg['db']}"
                    
                    logger.info(
                        "正在建立Redis连接",
                        host=self.redis_cfg['host'],
                        port=self.redis_cfg['port'],
                        db=self.redis_cfg['db']
                    )
                    self.redis = await redis.from_url(
                        redis_url,
                        encoding="utf-8",
                        decode_responses=True,
                    )
                    try:
                        await self.redis.ping()
                        self._initialized = True
                        logger.info(
                            "Redis连接建立成功",
                            host=self.redis_cfg['host'],
                            port=self.redis_cfg['port'],
                            db=self.redis_cfg['db']
                        )
                    except Exception as e:
                        logger.error(
                            "Redis连接失败",
                            host=self.redis_cfg['host'],
                            port=self.redis_cfg['port'],
                            error=str(e),
                            exc_info=True
                        )
                        self.redis = None
                        self._initialized = False
                        raise e
            except Exception as e:
                logger.error(
                    "Redis初始化失败",
                    error=str(e),
                    exc_info=True
                )
                raise e
    
    async def mark_deleted(self, message_id: str):
        """
        标记消息已被撤回
        
        Args:
            message_id: 消息 ID
        """
        key = f"{REDIS_KEY_PREFIX_DELETED}{message_id}"
        await self.redis.set(key, "1", ex=60)  # 60秒过期，防止占用空间
    
    async def is_deleted(self, message_id: str) -> bool:
        """
        查询消息是否被撤回
        
        Args:
            message_id: 消息 ID
        
        Returns:
            bool: 是否已被撤回
        """
        key = f"{REDIS_KEY_PREFIX_DELETED}{message_id}"
        return await self.redis.exists(key) == 1
    
    async def set_flag(self, key: str, value: str):
        """
        设置 Redis 中的标志位
        
        Args:
            key: 标志位键
            value: 标志位值
        """
        try:
            await self.redis.set(key, value, ex=REDIS_EXPIRE_TIME)
        except Exception as e:
            logger.error(
                "设置Redis标志位失败",
                key=key,
                value=value,
                error=str(e),
                exc_info=True
            )
    
    async def get_flag(self, key: str) -> str:
        """
        读取 Redis 中的标志位
        
        Args:
            key: 标志位键
        
        Returns:
            str: 标志位值，不存在返回 "init"
        """
        try:
            value = await self.redis.get(key)
            return value if value else "init"
        except Exception as e:
            logger.error(
                "读取Redis标志位失败",
                key=key,
                error=str(e),
                exc_info=True
            )
            return "init"
    
    async def close_redis(self):
        """关闭 Redis 连接（带锁保护）"""
        async with self._redis_lock:
            if self.redis:
                try:
                    await self.redis.close()
                    self.redis = None
                    self._initialized = False
                    logger.info("Redis连接池已关闭")
                except Exception as e:
                    logger.error(
                        "关闭Redis连接时出错",
                        error=str(e),
                        exc_info=True
                    )
    
    async def ensure_redis_connection(self):
        """
        确保 Redis 连接可用（健康检查）
        
        如果连接失效，自动重新初始化
        """
        if not self._initialized or not self.redis:
            await self.init_pools()
        else:
            try:
                await self.redis.ping()
            except Exception as e:
                logger.warning(
                    "Redis健康检查失败，准备重新初始化",
                    error=str(e)
                )
                await self.init_pools()


async def init_dao() -> AsyncMessageMemoryDAO:
    """
    初始化全局 DAO 实例（单例模式 + 异步锁）
    
    Returns:
        AsyncMessageMemoryDAO: 全局 DAO 实例
    """
    global dao, _dao_lock
    
    # 初始化全局锁
    if _dao_lock is None:
        _dao_lock = asyncio.Lock()
    
    # 使用异步锁确保只初始化一次
    async with _dao_lock:
        if dao is None:
            logger.info("开始初始化全局DAO实例")
            dao = AsyncMessageMemoryDAO()
            await dao.init_pools()
            logger.info("全局DAO实例初始化完成")
        else:
            # 确保连接有效
            await dao.ensure_redis_connection()
            logger.debug("DAO实例已存在，确认连接有效")
    
    return dao


async def get_dao() -> AsyncMessageMemoryDAO:
    """
    获取 DAO 实例（自动初始化）
    
    Returns:
        AsyncMessageMemoryDAO: DAO 实例
    """
    global dao
    if dao is None:
        await init_dao()
    else:
        # 确保连接有效
        await dao.ensure_redis_connection()
    return dao
