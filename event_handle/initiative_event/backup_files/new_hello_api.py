from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Literal
from openai import AsyncOpenAI
import uvicorn
import httpx
import random
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
import requests
import json
from greeting_module import generate_greeting

# 加载环境变量
# 获取当前文件所在目录
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"

# 加载环境变量，添加 override=True 确保覆盖现有变量
load_dotenv(env_path, override=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
        # logging.FileHandler('event_handler.log', encoding='utf-8')  # 输出到文件
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Event Handler API")

# 初始化 OpenAI 客户端
client = AsyncOpenAI(
    base_url="https://app.onerouter.pro/v1",
    api_key=os.getenv("OPENAI_API_KEY")
)

logger.info("Event Handler API 启动成功")


# 定义响应模型
class ErrorResponse(BaseModel):
    code: int
    message: str
    details: Optional[str] = None


class SuccessResponse(BaseModel):
    code: int = 200
    message: str
    data: dict


# 定义请求模型
class EventRequest(BaseModel):
    event_type: Literal["filter", "greet"]
    event_dict: dict

# 模拟点赞接口调用
async def call_like_api(message_id: str, group_id: str) -> dict:
    """
    调用点赞接口
    实际使用时替换为真实的API地址
    返回格式: {"success": bool, "error": str (可选)}
    """
    # 随机生成 vote_type (0-3)
    vote_type = str(random.randint(0, 3))
    # 固定用户ID为 "0"
    user_id = "0"

    logger.info(f"[点赞API] 开始调用 - message_id: {message_id}, user_id: {user_id}, vote_type: {vote_type}")

    try:
        # 示例：真实调用
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            payload = {
                "user_id": user_id,
                "message_id": message_id,
                "vote_type": vote_type,
                "group_id": group_id
            }
            response = await http_client.post(
                "http://192.168.10.20:8093/api/group_chat/message_vote_by_agnes",
                json=payload
            )
            if response.status_code != 200:
                logger.error(f"[点赞API] 调用失败 - status_code: {response.status_code}, message_id: {message_id}")
                return {"success": False, "error": f"API返回错误: {response.status_code}"}
            logger.info(f"[点赞API] 调用成功 - message_id: {message_id}, vote_type: {vote_type}")
            return {"success": True, "data": response.json()}

    except httpx.TimeoutException as e:
        logger.error(f"[点赞API] 超时 - message_id: {message_id}, error: {str(e)}")
        return {"success": False, "error": "点赞接口超时"}
    except Exception as e:
        logger.error(f"[点赞API] 异常 - message_id: {message_id}, error: {str(e)}", exc_info=True)
        return {"success": False, "error": f"点赞接口异常: {str(e)}"}





@app.post("/api/initiative/event")
async def handle_event(request: EventRequest):
    """
    处理不同类型的事件

    逻辑流程：
    1. 先判断 event_type（filter 或 greet）
    2. 根据类型从 event_dict 中提取对应参数
    3. 执行不同的操作：
       - filter: 调用点赞 API
       - greet: 调用 LLM 生成问候语

    参数:
        event_type: "filter" 或 "greet","ignore"
        event_dict: 包含具体事件数据的字典
            - filter: {"message_id": "xxx", "group_id": "xxx"}
            - greet: {"greet_type": "good_m"|"good_n", "user_name": "xxx"(可选)}
            -

    返回码说明:
        200: 成功
        400: 参数错误
        500: 服务器内部错误（API调用失败）
        503: LLM生成失败，已使用备用方案
    """
    # ===== 步骤1: 判断 event_type =====
    event_type = request.event_type
    event_dict = request.event_dict

    logger.info(f"[请求开始] event_type: {event_type}, event_dict: {event_dict}")

    # ===== 步骤2&3: 根据类型处理 =====
    if event_type == "filter":
        logger.info(f"[Filter事件] 开始处理")

        # 从 event_dict 提取 filter 所需参数
        message_id = event_dict.get("message_id")
        group_id = event_dict.get("group_id")

        # 参数校验
        if not message_id or not group_id:
            missing = "message_id" if not message_id else "group_id"
            logger.warning(f"[Filter事件] 参数缺失 - {missing}为空")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 400,
                    "message": "参数错误",
                    "details": f"filter 事件需要包含 message_id 和 group_id"
                }
            )

        # 调用点赞接口
        try:
            prob_str = os.getenv("LIKE_PROBABILITY", "1.0")
            execution_probability = float(prob_str)
        except ValueError:
            logger.error(f"环境变量 LIKE_PROBABILITY 格式错误: {prob_str}，回退到 1.0")
            execution_probability = 1.0

            # 3. 概率逻辑判断
        random_val = random.random()
        if random_val > execution_probability:
            logger.info(
                f"[Filter事件] 概率未命中 (随机值 {random_val:.2f} > 阈值 {execution_probability})，跳过点赞接口调用")
            return {
                "code": 200,
                "message": "未命中执行概率，已跳过点赞",
                "data": {
                    "event_type": "filter",
                    "action": "skipped",
                    "probability_threshold": execution_probability,
                    "random_value": round(random_val, 2)
                }
            }

        # 4. 执行点赞接口调用
        logger.info(f"[Filter事件] 概率命中 (随机值 {random_val:.2f} <= 阈值 {execution_probability})，正在调用接口")
        like_result = await call_like_api(message_id, group_id)

        # 判断 API 调用是否成功
        if not like_result.get("success", True):
            logger.error(f"[Filter事件] 点赞失败 - message_id: {message_id}, error: {like_result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": 500,
                    "message": "点赞API调用失败",
                    "details": like_result.get("error", "未知错误")
                }
            )

        # 成功返回
        logger.info(f"[Filter事件] 处理成功 - message_id: {message_id}")
        return {
            "code": 200,
            "message": "点赞成功",
            "data": {
                "event_type": "filter",
                "action": "like",
                "message_id": message_id,
                "result": like_result
            }
        }

    elif event_type == "greet":
        logger.info(f"[Greet事件] 开始处理")

        # 从 event_dict 提取 greet 所需参数
        greet_type = event_dict.get("greet_type")
        user_name = event_dict.get("user_name")
        language_code = event_dict.get("language_code")
        # 参数校验
        if not greet_type:
            logger.warning(f"[Greet事件] 参数缺失 - greet_type为空")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 400,
                    "message": "参数错误",
                    "details": "greet 事件的 event_dict 需要包含 greet_type"
                }
            )

        if greet_type not in ["good_m", "good_n"]:
            logger.warning(f"[Greet事件] 参数错误 - greet_type: {greet_type}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 400,
                    "message": "参数错误",
                    "details": f"greet_type 必须是 'good_m' 或 'good_n'，当前值: {greet_type}"
                }
            )

        # 调用 LLM 生成问候语
        greeting_result = await generate_greeting(greet_type, language_code, user_name)

        # 判断 LLM 生成是否成功
        if not greeting_result.get("success", False):
            # LLM 失败但使用了备用方案
            logger.warning(f"[Greet事件] LLM降级 - greet_type: {greet_type}, user_name: {user_name}")
            return {
                "code": 503,
                "message": "LLM生成失败，已使用备用问候语",
                "data": {
                    "event_type": "greet",
                    "greet_type": greet_type,
                    "user_name": user_name,
                    "greeting": greeting_result.get("greeting"),
                    "fallback": True,
                    "error": greeting_result.get("error")
                }
            }

        # 成功返回
        logger.info(f"[Greet事件] 处理成功 - greet_type: {greet_type}, user_name: {user_name}")
        return {
            "code": 200,
            "message": "问候语生成成功",
            "data": {
                "event_type": "greet",
                "greet_type": greet_type,
                "user_name": user_name,
                "greeting": greeting_result.get("greeting"),
                "fallback": False
            }
        }

    else:
        # 不支持的事件类型
        logger.warning(f"[请求失败] 不支持的事件类型 - event_type: {event_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": 400,
                "message": "不支持的事件类型",
                "details": f"event_type 必须是 'filter' 或 'greet'，当前值: {event_type}"
            }
        )


@app.get("/")
async def root():
    logger.info("[根路径] 访问API信息页面")
    return {
        "message": "Event Handler API",
        "endpoints": {
            "POST /api/initiative/event": "处理事件（filter 或 greet）"
        }
    }


# 添加启动和关闭事件
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 50)
    logger.info("Event Handler API 正在启动...")
    logger.info(f"OpenAI Base URL: {os.getenv('OPENAI_BASE_URL') or 'https://app.onerouter.pro/v1'}")
    logger.info(f"LLM Model: {os.getenv('LLM_CHAT_CHECK_MODEL') or 'gemini-2.5-flash'}")
    logger.info("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("=" * 50)
    logger.info("Event Handler API 正在关闭...")
    logger.info("=" * 50)


if __name__ == "__main__":
    config = uvicorn.Config(
        "hello_api:app",
        host="0.0.0.0",
        port=8800,
        reload=False
    )
    server = uvicorn.Server(config)
    server.run()
