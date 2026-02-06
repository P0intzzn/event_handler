"""
事件处理路由模块
处理 greet、commentary 等事件类型
"""
from fastapi import APIRouter, HTTPException, status

from app.routers.event.schemas import EventRequest
from app.routers.event.utils import params_check_commentary, params_check_greet, get_group_contexts_info, check_url_accessible
from services.external_api_service import send_message_api
from app.routers.event.content_generation_service import (generate_content,
                                                          get_fallback_content,
                                                          gen_template_commentary,
                                                          gen_template_commentary_v2)
from services.llm_service import AsyncLLMAgent
from storage.redis_helper import ChatStorageHelper
from utils.logger import logger

# 创建路由器
router = APIRouter()


@router.post("/event")
async def handle_event(request: EventRequest):
    """
    处理不同类型的事件
    
    逻辑流程：
    1. 先判断 event_type（commentary/greet）
    2. 根据类型从 event_dict 中提取对应参数
    3. 执行不同的操作：
        - commentary: 生成点评内容并回复消息
        - greet: 生成问候语
    
    Args:
        request: EventRequest 请求模型
            - event_type: "commentary"/"greet"
            - event_dict: 包含具体事件数据的字典
    
    Returns:
        Dict: {"code": int, "message": str, "data": dict}
    
    Raises:
        HTTPException: 参数错误或服务调用失败时抛出
    """
    event_type = request.event_type
    event_dict = request.event_dict
    
    logger.info("Event 响应事件处理请求", event_type=event_type, event_dict=event_dict)

    # 提取参数
    user_name = event_dict.user_name
    group_id = event_dict.group_id
    language_code = event_dict.language_code

    rst_data = {
        "event_type": event_type,
        "greet_type": None,
        "user_name": user_name,
        "language_code": language_code,  # 早安/晚安场景必须更新
        "greeting": None,
        "fallback": False
    }  # 初始化rsp_data

    # ============ Greet 事件：生成问候语 ============
    if "greet" == event_type:
        greet_type = event_dict.greet_type
        festival_name = event_dict.festival_name  # 仅good_f用到
        
        # 参数校验
        params_check_greet(greet_type=greet_type, festival_name=festival_name)
        rst_data["greet_type"] = greet_type
        
        # 根据group_id获取上下文
        logger.info("Greet事件获取上下文", group_id=group_id, greet_type=greet_type, festival_name=festival_name)
        if greet_type in ["good_m", "good_n"]:  # 早安/晚安 特殊处理
            topic = event_dict.topic
            push_type = event_dict.push_type
            push_value = event_dict.push_value[:200]  # 限制推送内容长度

            contexts_str = f"push_type: {push_type}, push_value: {push_value}"
            logger.info(
                "Greet 事件根据推送内容生成问候语",
                group_id=group_id,
                contexts_preview=contexts_str[:100] if contexts_str else "",
                push_type=push_type,
                topic=topic
            )
            greeting_result = await generate_content(greet_type,
                                                     language_code=language_code,
                                                     user_name=user_name,
                                                     contexts=contexts_str,
                                                     topic=topic)

            # contexts_info = await get_group_contexts_info(group_id, True)
            # if not contexts_info.get("success", False):
            #     logger.warning("Greet事件获取上下文失败", group_id=group_id, greet_type=greet_type)
            #     contexts_str = ""
            # else:
            #     contexts_str = contexts_info.get("contexts_str", "")
            #     # 补充群聊上下文信息进rst_data
            #     info_dict = contexts_info.get("context_info", {})
            #     rst_data["focal_figure"] = info_dict.get("focal_figure")
            #     rst_data["topic_hot"] = info_dict.get("topic_hot")
            #     rst_data["topic_ext"] = info_dict.get("topic_ext")
            #     if info_dict.get("contexts_language"):
            #         rst_data["language_code"] = info_dict["contexts_language"]
            #     logger.info("Greet事件获取上下文成功", group_id=group_id, info_dict=info_dict)
        else:
            group_contexts = await ChatStorageHelper.get_group_context(group_id)
            contexts_str = ChatStorageHelper.context_list_to_str(group_contexts)
            logger.info(
                "Greet事件根据上下文生成问候语",
                greet_type=greet_type,
                group_id=group_id,
                contexts_preview=contexts_str[:100] if contexts_str else "",
                context_count=len(group_contexts)
            )
            # 根据不同greet_type调用LLM生成问候语
            greeting_result = await generate_content(greet_type,
                                                     festival_name=festival_name,
                                                     language_code=language_code,
                                                     user_name=user_name,
                                                     contexts=contexts_str)

        rst_data["greeting"] = greeting_result.get("greeting")

        logger.info("LLM生成问候语完成", 
            greet_type=greet_type, 
            is_success=greeting_result.get("success", False),
            has_contexts=bool(len(contexts_str)),
            greeting=greeting_result.get("greeting"),
            fallback=greeting_result.get("fallback", False)
        )

    else:  # commentary
        message_id = event_dict.message_id
        template_flag = event_dict.is_template
        input_urls = event_dict.user_upload_url
        output_url = event_dict.s3_url

        user_prompt = event_dict.prompt

        # 参数校验
        params_check_commentary(event_dict=event_dict)
        
        # 调用LLM生成点评
        if template_flag:
            logger.info("Commentary点评模板生成物",
                        input_urls=input_urls,
                        output_url=output_url,
                        language_code=language_code,
                        group_id=group_id,
                        message_id=message_id
                        )

            # 检查url是否可用
            for url in (input_urls + [output_url]):
                is_avail, err_detail = await check_url_accessible(url)
                if not is_avail:
                    logger.warning("Commentary事件检查输出URL可用性失败", url=url, err_detail=err_detail)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "code": 400,
                            "message": f"URL{url}不可用",
                            "details": err_detail
                        }
                    )
            # 限制输入URL数量的最大值（避免处理过多图片导致性能问题）
            INPUT_URL_MAX = 5  # 最大支持的输入URL数量
            # 如果输入URL数量超过限制，只保留前N个
            if len(input_urls) > INPUT_URL_MAX:
                original_count = len(input_urls)
                input_urls = input_urls[:INPUT_URL_MAX]
                logger.info(
                    "输入URL数量超过限制，已截断",
                    original_count=original_count,
                    max_limit=INPUT_URL_MAX
                )

            # 根据group_id获取上下文
            group_contexts = await ChatStorageHelper.get_group_context_all(group_id)
            contexts_str = ChatStorageHelper.context_list_to_str(group_contexts)
            
            if contexts_str:
                logger.info("Commentary 通过上下文识别语言", group_id=group_id, contexts_preview=contexts_str[:100],
                            context_count=len(group_contexts))
                llm_inst = AsyncLLMAgent()
                language_code_llm = await llm_inst.recognize_language(context=contexts_str)
                language_code = language_code_llm
                rst_data["language_code"] = language_code  # 更新language_code

            # greeting_result = await gen_template_commentary(input_urls, output_url, language_code)
            greeting_result = await gen_template_commentary_v2(input_urls, output_url, language_code)

            if not greeting_result.get("success", False):
                greeting_result["greeting" ]= get_fallback_content(event_type, language_code)
                greeting_result["fallback"] = True

        else:  # prompt 生成物
            logger.info("Commentary点评提示词生成物", prompt_preview=user_prompt[:100], language_code=language_code,
                        group_id=group_id, message_id=message_id)
            greeting_result = await generate_content(event_type,
                                                    language_code=language_code,
                                                    generate_prompt=user_prompt)

        # 更新rst_data
        rst_data["greeting"] = greeting_result.get("greeting")
        rst_data["fallback"] = greeting_result.get("fallback", False)

        logger.info(
            "LLM点评生成完成",
            template_flag=template_flag,
            success=greeting_result.get("success", False),
            greet_preview=greeting_result.get("greeting")[:100],
            fallback=greeting_result.get("fallback", False)
        )

        # 点评事件无论生成是否成功，都发送消息
        send_result = await send_message_api(message_id, group_id, greeting_result.get("greeting"))
        if not send_result.get("is_success", True):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": 500,
                    "message": "发消息API调用失败",
                    "details": send_result.get('err_msg', "未知错误")
                }
            )

    # 判断 LLM 生成是否成功
    if not greeting_result.get("success", False):
        # LLM 失败但使用了备用方案
        logger.warning(
            "Event事件LLM降级",
            event_type=event_type,
            greet_type=event_dict.greet_type,
            user_name=user_name,
            error=greeting_result.get('error'),
        )
        return {
            "code": 200,
            "message": "LLM生成失败，已使用备用生成内容",
            "data": rst_data
        }

    # 成功返回
    logger.info(
        "Event事件处理成功",
        event_type=event_type,
        group_id=group_id,
        greet_type=event_dict.greet_type
    )
    return {
        "code": 200,
        "message": "问候语生成成功",
        "data": rst_data
    }


@router.get("/event")
async def root():
    """API 信息页"""
    logger.info("访问Event Handle信息页面")
    return {
        "message": "Event Handler API",
        "endpoints": {
            "POST /api/initiative/event": "处理事件 greet 或 commentary",
            "GET /api/initiative/event": "Event Handler API 信息页"
        }
    }
