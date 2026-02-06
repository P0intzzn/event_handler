"""
事件处理工具方法

"""
import os
import httpx
import random
import asyncio
from fastapi import HTTPException, status
from typing import Tuple

from app.routers.event import event_const
from app.routers.event.schemas import EventDict
import const
from utils.logger import logger

def params_check_commentary(event_dict: EventDict) -> None:
    """
    参数检查，检查 Commentary 事件的参数是否合法

    Args:
        event_dict: EventDict

    """
    template_flag = event_dict.is_template

    # 检查是否有template_flag, 如果有则检查input_urls(list[str]), output_url(str), 如果没有则检查user_prompt(str)
    if template_flag:
        if not event_dict.user_upload_url or not all(isinstance(url, str) for url in event_dict.user_upload_url) \
            or not event_dict.s3_url:
            logger.warning(
                "Commentary事件url缺失",
                template_flag=template_flag,
                input_urls=event_dict.user_upload_url,
                output_url=event_dict.s3_url
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 400,
                    "message": "参数错误",
                    "details": "commentary 事件的 event_dict 需要包含 user_upload_url 和 s3_url"
                }
            )
    else:
        # 非模板生成物依赖生成提示词
        if not event_dict.prompt:  
            logger.warning(
                "Commentary事件prompt缺失",
                template_flag=template_flag,
                user_prompt=event_dict.prompt
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 400,
                    "message": "参数错误",
                    "details": "commentary 事件的 event_dict 需要包含 prompt"
                }
            )

def params_check_greet(greet_type: str, festival_name: str = None) -> None:
    """
    参数检查，检查 Greet 事件的参数是否合法

    Args:
        greet_type: 问候类型
        festival_name: 节日名称
    """
    # group_id 和 greet_type 由pydantic模型检查

    if greet_type not in event_const.GREETING_TYPES:
        logger.warning("Greet事件greet_type错误", greet_type=greet_type)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": 400,
                "message": "参数错误",
                "details": f"greet_type 必须是 {event_const.GREETING_TYPES} 中的一个，当前值: {greet_type}"
            }
        )
    elif "good_f" == greet_type and not (festival_name and festival_name in event_const.FESTIVALS):
        logger.warning("Greet事件节日类型错误", greet_type=greet_type, festival_name=festival_name)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": 400,
                "message": "参数错误",
                "details": f"节日类型不符合要求，当前值: {festival_name}"
            }
        )


def check_execution_probability_with_details(probability_env_var: str = "LIKE_PROBABILITY",
                                            default_probability: float = 0.5) -> tuple[bool, float, float]:
    """
    检查执行概率，决定是否执行某个操作，并返回详细信息

    Args:
        probability_env_var: 环境变量名，用于获取执行概率
        default_probability: 默认执行概率

    Returns:
        tuple[bool, float, float]: (是否应该执行, 随机值, 阈值)
    """
    try:
        prob_str = os.getenv(probability_env_var, str(default_probability))
        execution_probability = float(prob_str)
    except ValueError:
        logger.error(f"环境变量 {probability_env_var} 格式错误: {prob_str}，回退到 {default_probability}")
        execution_probability = default_probability

    random_val = random.random()

    should_execute = random_val <= execution_probability
    if not should_execute:
        logger.info(
            f"概率未命中 (随机值 {random_val:.2f} > 阈值 {execution_probability})，跳过执行"
        )
    else:
        logger.info(
            f"概率命中 (随机值 {random_val:.2f} <= 阈值 {execution_probability})，执行操作"
        )

    return should_execute, random_val, execution_probability

async def get_group_contexts_info(group_id:str, need_context: bool = False) -> dict:
    """
    获取群组上下文信息

    Args:
        group_id: 群组ID
        need_context: 是否需要上下文内容

    Returns:
        dict: 群组上下文信息，包含以下字段：
            - success (bool): 是否成功获取群组上下文信息
            - context_info (dict): 上下文信息，包含：
                - focal_figure (str): 焦点人物
                - topic_hot (str): 热门话题
                - topic_ext (str): 扩展话题
                - contexts_language (str): 上下文语言
            - contexts_str (Optional[str]): 完整上下文字符串（仅当need_context=True时返回）
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            payload = {
                "group_id": group_id,
                "has_context": need_context,
            }
            response = await http_client.get(const.GET_CONTEXT_INFO_URL, params=payload)
            
            if response.status_code != 200:
                logger.error("获取群聊信息失败", group_id=group_id, status_code=response.status_code,
                    response_text=response.text)
                return {
                    "success": False,
                    "context_info": {
                        "focal_figure": None,
                        "topic_hot": None,
                        "topic_ext": None,
                        "contexts_language": "en"
                    },
                    "contexts_str": None
                }
            
            logger.info("获取群聊信息成功", group_id=group_id, response_text=response.text)
            
            # 解析响应JSON
            response_data = response.json()
            return {
                "success": True,
                "context_info": response_data.get("context_info", {}),
                "contexts_str": response_data.get("contexts_str", None)
            }
    except Exception as e:
        logger.error("调用群聊信息接口异常", group_id=group_id, error=str(e), url=const.GET_CONTEXT_INFO_URL)
        return {
            "success": False,
            "context_info": {
                "focal_figure": None,
                "topic_hot": None,
                "topic_ext": None,
                "contexts_language": "en"
            },
            "contexts_str": None
        }

def is_video_url(url: str) -> bool:
    """
    判断给定的URL是否指向视频文件

    Args:
        url: 要检查的URL字符串
    Returns:
        bool: 如果URL指向视频文件则返回True，否则返回False
    """
    # 输入类型检查
    if not isinstance(url, str):
        raise TypeError(f"Expected url to be a string, got {type(url).__name__}")
    
    # 支持的视频文件扩展名集合（使用集合提高查询效率）
    VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm', '.mpeg', '.mpg', '.3gp', '.ogg'}
    
    # 获取文件扩展名并转换为小写（处理大小写不敏感的情况）
    # 使用rsplit从右侧分割，确保处理包含多个点的URL
    file_ext = url.lower().rsplit('.', 1)[-1] if '.' in url else ''
    file_ext_with_dot = f".{file_ext}"
    
    # 直接返回判断结果
    return file_ext_with_dot in VIDEO_EXTENSIONS


async def check_url_accessible(
    url: str,
    timeout: float = 10.0,
    retry: int = 1,                 # 只 retry 一次
    retry_delay: float = 1.0,       # 重试前 sleep 秒
) -> Tuple[bool, str]:
    """
    返回: (是否可用, 失败原因)
    - retry: 失败后最多重试次数（默认 1 次）
    """

    async def _do_head() -> httpx.Response:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=0),
        ) as client:
            return await client.head(url)

    last_error: str = ""

    for attempt in range(retry + 1):  # 第 0 次是原始请求
        try:
            resp = await _do_head()

            # 2xx 才算成功
            if resp.status_code == 200:
                return True, "ok"

            # 4xx 基本无意义重试（除非你有鉴权刷新机制）
            if 400 <= resp.status_code < 500:
                return False, f"HTTP {resp.status_code}"

            # 5xx：可 retry
            last_error = f"HTTP {resp.status_code}"

        except httpx.TimeoutException:
            last_error = "timeout"
        except httpx.RequestError as e:
            last_error = f"request error: {e}"

        # 如果还有重试机会，sleep 一下
        if attempt < retry:
            await asyncio.sleep(retry_delay)

    return False, last_error


def build_m_n_policy(
        contexts: str,
        language_code: str
):
    """
        构建语言策略

        Args:
            contexts: 语言字符串
            language_code: 语言代码

        Returns:
            str: 语言策略
        """

    return f"""
        - Write the output strictly in: {language_code}.
        - You MUST base the “topic or content you will bring up or share” on the given context.
        - The push_value and push_type should be clearly implied in the greeting.
        - DO NOT mention “push_value”, “push_type”, “context”, or any system terms.
        """

