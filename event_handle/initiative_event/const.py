"""
全局常量定义模块

将所有硬编码常量集中管理，优先从环境变量读取
优先级：环境变量 > const.py 默认值
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 加载环境变量
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
load_dotenv(env_path, override=True)


# ==================== API 地址配置 ====================
AGNES_API_URL: str = os.getenv("SEND_REQ_URL")
LIKE_API_URL: str = f"{AGNES_API_URL}/api/group_chat/message_vote_by_agnes"
SEND_MESSAGE_API_URL: str = f"{AGNES_API_URL}/api/group_chat/send_message"


# ==================== 超时配置 ====================
HTTP_TIMEOUT: float = float(os.getenv("HTTP_TIMEOUT", "180.0"))
LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "180.0"))


# ==================== LLM 配置 ====================
DEFAULT_LLM_MODEL: str = os.getenv(
    "LLM_CHAT_CHECK_MODEL",
    "gemini-2.5-flash"
)

GREET_LLM_MODEL: str = os.getenv(
    "LLM_CHAT_CHECK_MODEL",
    "gemini-2.5-flash"
)

LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "1.2"))

OPENAI_BASE_URL: str = os.getenv(
    "OPENAI_BASE_URL",
    "https://app.onerouter.pro/v1"
)

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")


# ==================== 问候语配置 ====================
MAX_GREETING_LENGTH_CJK: int = 70  # 临时设置，后续恢复env配置
MAX_GREETING_LENGTH_EN: int = 50
# MAX_GREETING_LENGTH_CJK: int = int(os.getenv("MAX_GREETING_LENGTH_CJK", "35"))
# MAX_GREETING_LENGTH_EN: int = int(os.getenv("MAX_GREETING_LENGTH_EN", "25"))

# ==================== 点赞配置 ====================
LIKE_PROBABILITY: float = float(os.getenv("LIKE_PROBABILITY", "1"))


# ==================== Redis 配置 ====================
REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")

REDIS_KEY_PREFIX_GROUP: str = "group_context:"
REDIS_KEY_PREFIX_USER: str = "user_context:"
REDIS_KEY_PREFIX_GROUP_ALL: str = "group_context_all:"
REDIS_KEY_PREFIX_DELETED: str = "deleted:"

REDIS_EXPIRE_TIME: int = int(os.getenv("REDIS_EXPIRE_TIME", "180"))


# ==================== 应用配置 ====================
APP_TITLE: str = "Event Handler API"
APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT: int = int(os.getenv("APP_PORT", "8800"))


# ==================== 日志配置 ====================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = os.getenv("LOG_FILE", "logs/event_handler.log")


# ==================== Prompts 目录配置 ====================
PROMPTS_DIR: Path = BASE_DIR / "prompts"

# ==================== Mem 交互配置 ====================
MEM_SERVER_URL: str = os.getenv("MEM_SERVER_URL", "127.0.0.1")  # env待补充
MEM_SERVER_PORT: int = int(os.getenv("MEM_SERVER_PORT", "8000"))
GET_CONTEXT_INFO_URL: str = f"http://{MEM_SERVER_URL}:{MEM_SERVER_PORT}/api/v1/memories/contexts/infos"
