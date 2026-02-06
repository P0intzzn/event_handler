"""
外部 API 调用服务模块

提供点赞、发送消息等外部 API 调用功能
"""
from typing import Union

import httpx

from utils.logger import logger
from const import LIKE_API_URL, SEND_MESSAGE_API_URL, HTTP_TIMEOUT


async def call_like_api(message_id: str, group_id: str, vote_type: str) -> dict[str, Union[bool, dict, str]]:
    """
    调用点赞接口
    
    Args:
        message_id: 消息 ID
        group_id: 群组 ID
        vote_type: 点赞类型 (0-5 的字符串)
    
    Returns:
        dict: {"success": bool, "data": dict (可选), "error": str (可选)}
    
    Examples:
        - result = await call_like_api("msg_123", "group_456")
        - result["success"]
        True
    """
    # 固定用户ID为 "0"
    user_id = "0"
    
    logger.info(
        "点赞API调用开始",
        message_id=message_id,
        group_id=group_id,
        user_id=user_id,
        vote_type=vote_type,
    )
    
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as http_client:
            payload = {
                "user_id": user_id,
                "message_id": message_id,
                "vote_type": vote_type,
                "group_id": group_id
            }
            response = await http_client.post(
                LIKE_API_URL,
                json=payload
            )
            if response.status_code != 200:
                logger.error(
                    "点赞API调用失败",
                    message_id=message_id,
                    group_id=group_id,
                    status_code=response.status_code,
                )
                return {"success": False, "error": f"API返回错误: {response.status_code}"}
            logger.info(
                "点赞API调用成功",
                message_id=message_id,
                group_id=group_id,
                vote_type=vote_type,
            )
            return {"success": True, "data": response.json()}
    
    except httpx.TimeoutException as e:
        logger.error(
            "点赞API超时",
            message_id=message_id,
            group_id=group_id,
            error=str(e),
        )
        return {"success": False, "error": "点赞接口超时"}
    except Exception as e:
        logger.error(
            "点赞API异常",
            message_id=message_id,
            group_id=group_id,
            error=str(e),
            exc_info=True,
        )
        return {"success": False, "error": f"点赞接口异常: {str(e)}"}


async def send_message_api(message_id: str, group_id: str, content: str) -> dict[str, Union[bool, dict, str]]:
    """
    调用发消息接口
    
    Args:
        message_id: 消息 ID（作为 parent_id）
        group_id: 群组 ID
        content: 消息内容
    
    Returns:
        dict: {"is_success": bool, "err_msg": dict | str}
    
    Examples:
        - result = await send_message_api("msg_123", "group_456", "Hello!")
        - result["is_success"]
        True
    """
    logger.info(
        "发消息API调用开始",
        message_id=message_id,
        group_id=group_id,
        content_length=len(content),
    )
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            payload = {
                "group_id": group_id,
                "content": content,
                "parent_id": message_id,
            }
            response = await http_client.post(
                SEND_MESSAGE_API_URL,
                json=payload
            )
            if response.status_code != 200:
                logger.error(
                    "发消息API调用失败",
                    url=SEND_MESSAGE_API_URL,
                    message_id=message_id,
                    group_id=group_id,
                    status_code=response.status_code,
                )
                return {"is_success": False, "err_msg": f"API返回错误: {response.status_code}"}
            logger.info(
                "发消息API调用成功",
                message_id=message_id,
                group_id=group_id,
            )
            return {"is_success": True, "err_msg": response.json()}
    except httpx.TimeoutException as e:
        logger.error(
            "发消息API超时",
            message_id=message_id,
            group_id=group_id,
            error=str(e),
        )
        return {"is_success": False, "err_msg": "发消息接口超时"}
    except Exception as e:
        logger.error(
            "发消息API异常",
            message_id=message_id,
            group_id=group_id,
            error=str(e),
            exc_info=True,
        )
        return {"is_success": False, "err_msg": f"发消息接口异常: {str(e)}"}
