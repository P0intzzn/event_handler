"""
互动处理路由模块
处理 message、others 等互动类型
"""
import random
from typing import Union
from fastapi import APIRouter, HTTPException, status

import const
from app.routers.interact.interact_utils import analyze_message
from app.routers.interact.schemas import InteractRequest
from services.external_api_service import call_like_api
from utils.logger import logger
from utils.common import check_probability_threshold

# 创建路由器
router = APIRouter()


@router.post("/interaction")
async def handle_msg_interact(request: InteractRequest) -> dict[str, Union[str, int, dict]]:
    """
    处理消息互动判断

    Args:
        request: 互动请求对象
            - msg_type: "message" (消息) / "others" (其他)
            - msg_dict: 包含 message_id, group_id, contents (可选), is_agnes 

    Returns:
        dict: 返回处理结果
            - code: 200 (成功) / 400 (参数错误) / 500 (内部错误)
            - message: 描述信息
            - data: 结果数据

    Raises:
        HTTPException: 参数错误或内部错误时抛出
    """
    msg_type = request.msg_type
    msg_dict = request.msg_dict

    # Pydantic 已完成基础参数校验
    message_id = msg_dict.message_id
    group_id = msg_dict.group_id
    is_agnes = msg_dict.is_agnes

    logger.info(
        "Interact接口请求开始", msg_type=msg_type, message_id=message_id, group_id=group_id, is_agnes=is_agnes
    )

    if msg_type == "message":
        contents = msg_dict.contents

        if is_agnes:
            logger.info("Interact接口跳过系统消息", reason="系统消息无需判断")
            return {
                "code": 200,
                "message": "系统消息无需互动",
                "data": {
                    "msg_type": "message",
                    "message_id": message_id,
                    "group_id": group_id,
                    "action": "skipped",
                    "is_agnes": is_agnes
                }
            }

        # 根据消息内容，选择不同emoji
        is_bystander = "@Agnes" not in contents
        vote_type = await analyze_message(contents, is_bystander)

        if vote_type in {0, 2, 3, 4, 5}:
            logger.info(
                "Interact LLM识别完成",
                contents=contents,
                vote_type=vote_type,
                message_id=message_id,
                group_id=group_id
            )
        elif 6 == vote_type:
            logger.info(
                "Interact 跳过中性消息",
                contents=contents,
                vote_type=vote_type,
                message_id=message_id,
                group_id=group_id,
                reason="中性消息无需点赞"
            )
            return {
                "code": 200,
                "message": "中性消息，已跳过点赞",
                "data": {
                    "msg_type": "message",
                    "message_id": message_id,
                    "group_id": group_id,
                    "action": "skipped",
                    "msg_emotions": vote_type,
                }
            }
        else:
            logger.error(
                "Interact LLM识别失败",
                vote_type=vote_type,
                contents=contents,
                message_id=message_id,
                group_id=group_id
            )
            return {
                "code": 500,
                "message": "消息互动失败",
                "detail": f"LLM识别失败，vote_type: {vote_type}"
            }

        # message 点赞增加随机性
        random_prob = 0.8
        random_rst, random_val = check_probability_threshold(random_prob)
        # 旁观者场景才启用随机性，@Agnes 场景不使用随机性
        if is_bystander and not random_rst:
            logger.info(
                "Interact 概率未命中跳过点赞",
                random_value=round(random_val, 2),
                threshold=random_prob,
                message_id=message_id,
                group_id=group_id,
                reason="旁观者场景随机性控制"
            )
            return {
                "code": 200,
                "message": "未命中执行概率，已跳过点赞",
                "data": {
                    "msg_type": "message",
                    "action": "skipped",
                    "probability_threshold": random_prob,
                    "random_value": round(random_val, 2)
                }
            }
        logger.info("Interact message需执行点赞", vote_type=vote_type, message_id=message_id, group_id=group_id)
    else:  # "others"
        # 系统消息无需判断
        if is_agnes:
            logger.info(
                f"[Interact接口] 系统消息无需判断 - is_agnes: {is_agnes}, message_id: {message_id}, group_id: {group_id}")
            return {
                "code": 200,
                "message": "系统消息无需判断",
                "data": {
                    "msg_type": "others",
                    "message_id": message_id,
                    "action": "skipped",
                    "is_agnes": is_agnes
                }
            }

        # 概率判断逻辑，决定是否执行点赞
        random_rst, random_val = check_probability_threshold(const.LIKE_PROBABILITY)
        if not random_rst:
            logger.info(
                "Interact 非文本消息，概率未命中跳过点赞",
                random_value=round(random_val, 2),
                threshold=const.LIKE_PROBABILITY,
                message_id=message_id,
                group_id=group_id,
            )
            return {
                "code": 200,
                "message": "未命中执行概率，已跳过点赞",
                "data": {
                    "msg_type": "others",
                    "action": "skipped",
                    "probability_threshold": const.LIKE_PROBABILITY,
                    "random_value": round(random_val, 2)
                }
            }
        vote_type = random.randint(0, 3)
        logger.info(
            "Interact others需执行点赞",
            vote_type=vote_type,
            random_value=round(random_val, 2),
            threshold=const.LIKE_PROBABILITY,
            message_id=message_id,
            group_id=group_id,
        )
        

    # 执行点赞调用
    vote_type_str = str(vote_type)
    like_result = await call_like_api(message_id, group_id, vote_type_str)
    if not like_result.get("success", False):
        logger.error(
            "Interact 点赞API调用失败",
            error=like_result.get('error', '未知错误'),
            message_id=message_id,
            group_id=group_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 500,
                "message": "点赞API调用失败",
                "details": like_result.get("error", "未知错误")
            }
        )

    logger.info(
        "Interact 点赞成功", vote_type=vote_type_str, msg_type=msg_type, message_id=message_id, group_id=group_id,
    )
    return {
        "code": 200,
        "message": "点赞成功",
        "data": {
            "msg_type": msg_type,
            "action": "liked",
            "message_id": message_id,
            "group_id": group_id,
            "vote_type": vote_type_str
        }
    }


@router.get("/interaction")
def interact_root():
    """Interact接口信息页"""
    logger.info("访问Interact接口信息页面")
    return {
        "message": "Interact API",
        "endpoints": {
            "POST /api/initiative/interaction": "处理消息互动",
            "GET /api/initiative/interaction": "Interact接口信息页"
        }
    }
