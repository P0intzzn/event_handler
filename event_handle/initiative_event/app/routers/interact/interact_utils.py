"""
互动事件工具方法
"""
from typing import Optional

from openai import AsyncOpenAI

from utils.logger import logger
from utils.prompt_utils import load_prompt_config
import const


# 加载消息分析提示词模板
_MESSAGE_ANALYZE_PROMPTS = load_prompt_config("message_analyze_prompts.json")

def _set_identity_role(*, is_bystander: bool) -> tuple[str, str]:
    """
    is_bystander=True  : 旁观者视角(群聊里友好互动)
    is_bystander=False : 当事人视角(用户@AI,对AI说话;强调降温、礼貌)
    """
    prompts = _MESSAGE_ANALYZE_PROMPTS.get("en", {})
    
    if is_bystander:
        role_block = prompts.get("role_bystander", "")
        extra_rules = prompts.get("extra_rules_bystander", "")
    else:
        role_block = prompts.get("role_mentioned", "")
        extra_rules = prompts.get("extra_rules_mentioned", "")

    return role_block, extra_rules

async def analyze_message(message_content: str,
                        is_bystander: bool,
                        client: Optional[AsyncOpenAI] = None,
                        contexts: Optional[str] = None) -> int:
    """
    输入：
        message_content： 消息文本
        is_bystander： 是否作为旁观者
            - True  = 旁观者视角（不是对AI说话）
            - False = @AI 场景（对AI说话，强调降温）
        client: OpenAI客户端（可选）
        contexts: 上下文（可选）

    输出 0-6：
        0 = thumbs-up (approval/encouragement)
        2 = laugh (funny)
        3 = surprised (wow/shock/astonishment)
        4 = crying (upset/apologetic)
        5 = angry (dissatisfaction)
        6 = normal (others/neutral/unclear)
    返回：0-6（int）
    """
    content = (message_content or "").strip()
    if not content:
        return 6

    contexts = (contexts or "").strip()
    role_block, extra_rules = _set_identity_role(is_bystander=is_bystander)  # 角色设定
    
    # 从JSON模板加载提示词模板
    prompts = _MESSAGE_ANALYZE_PROMPTS.get("en", {})
    template = prompts.get("template", "")
    
    # 填充模板变量
    prompt = template.format(
        role_block=role_block,
        extra_rules=extra_rules,
        contexts=contexts,
        content=content
    )

    if client is None:
        # 创建 OpenAI 客户端
        client = AsyncOpenAI(
            api_key=const.OPENAI_API_KEY,
            base_url=const.OPENAI_BASE_URL
        )

    try:
        completion = await client.chat.completions.create(
            model=const.DEFAULT_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,  # 分类更稳定
            timeout=const.LLM_TIMEOUT
        )
        raw = (completion.choices[0].message.content or "").strip()
        return _parse_label(raw)

    except Exception as e:
        logger.error(
            "Reaction LLM调用异常",
            error=str(e),
            message_content=content[:100] if content else None,
            exc_info=True
        )
        return 6


def _parse_label(raw_output: str) -> int:
    """
    解析模型输出为情感标签
    
    Args:
        raw_output: 模型原始输出
    
    Returns:
        int: 0-6 的情感标签，解析失败返回 6
    """
    try:
        label = int(raw_output.strip())
        if label in {0, 2, 3, 4, 5, 6}:
            return label
        logger.warning(
            "Reaction非法标签值",
            label=label,
            raw_output=raw_output,
            fallback_value=6
        )
        return 6
    except ValueError:
        logger.warning(
            "Reaction无法解析标签",
            raw_output=raw_output,
            fallback_value=6
        )
        return 6