"""
内容生成服务模块

提供个性化内容生成功能，包括问候语和点评内容，支持多语言和备用方案
"""
import json
import random
from typing import Optional, Dict
from openai import AsyncOpenAI
from fastapi import HTTPException

from utils.logger import logger

from utils.language_utils import normalize_language_code, is_cjk_language, language_dict, build_lang_policy
from const import (
    PROMPTS_DIR,
    GREET_LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
    MAX_GREETING_LENGTH_CJK,
    MAX_GREETING_LENGTH_EN,
    OPENAI_API_KEY,
    OPENAI_BASE_URL
)
from app.routers.event.commentary_template import PipelineV2
from app.routers.event.commentary_url import call_gemini_compare_and_comment
from app.routers.event.templates.fallback_templates import fallback_templates
from app.routers.event.templates.example_templates import example_templates
from app.routers.event.utils import is_video_url, build_m_n_policy


class ContentPromptManager:
    """内容生成 Prompt 管理器"""
    
    def __init__(self):
        """初始化 Prompt 管理器，加载配置文件"""
        self.greeting_prompts = self._load_prompts("greeting_prompts.json")
        self.commentary_prompts = self._load_prompts("commentary_prompts.json")
        self.greet_m_n_prompts = self._load_prompts("greet_m_n_prompts.json")

    @staticmethod
    def _load_prompts(filename: str) -> Dict[str, dict]:
        """
        加载 prompt 配置文件
        
        Args:
            filename: 配置文件名
        
        Returns:
            Dict[str, dict]: 配置字典
        """
        file_path = PROMPTS_DIR / filename
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(
                    "Prompt配置文件加载成功",
                    filename=filename,
                )
                return data
        except FileNotFoundError:
            logger.error(
                "Prompt配置文件不存在",
                filename=filename,
                file_path=str(file_path),
            )
            return {}
        except json.JSONDecodeError as e:
            logger.error(
                "Prompt配置文件JSON解析失败",
                filename=filename,
                error=str(e),
            )
            return {}
    
    def get_prompt(
        self,
        content_type: str,
        festival_name: Optional[str],
        language_code: Optional[str],
        user_name: Optional[str] = None,
        contexts: Optional[str] = None
    ) -> Optional[str]:
        """
        获取指定类型的 prompt
        
        Args:
            content_type: 内容类型 "good_m"/"good_n"/"good_l"/"good_w"/"good_f"/"commentary"
            festival_name: 节日名
            language_code: 语言代码（用于生成内容的语言）
            user_name: 用户名（可选）
            contexts: 上下文（可选）
        
        Returns:
            Optional[str]: 构建好的 prompt 字符串
        """
        # 选择对应的 prompts 配置（仅使用英文提示词）
        if "good_m" == content_type or "good_n" == content_type:
            prompts_dict = self.greet_m_n_prompts
        elif "commentary" == content_type:
            prompts_dict = self.commentary_prompts
        else:
            prompts_dict = self.greeting_prompts
        prompts_conf = prompts_dict.get('en', {})
        
        if not prompts_conf:
            logger.error("Prompt配置错误无可用提示词")
            return None

        # 获取模板
        prompt_template = prompts_conf.get("template", "")
        if not prompt_template:
            logger.error("Prompt配置错误缺少template")
            return None
        # 随机选择一个风格
        styles = prompts_conf.get("styles", [])
        if not styles:
            logger.error("Prompt配置错误无可用风格")
            return None
        selected_style = random.choice(styles)

        # 根据上下文/prompts或language_code指定输出语种
        if "good_m" == content_type or "good_n" == content_type:
            lang_policy = build_m_n_policy(contexts, language_code)
        else:
            lang_policy = build_lang_policy(contexts, language_code, language_dict)
        
        # 处理用户名部分
        user_part_with_name = prompts_conf.get("user_part_with_name", "")
        user_part_without_name = prompts_conf.get("user_part_without_name", "")
        if user_name and user_part_with_name:
            user_part = user_part_with_name.format(user_name=user_name)
        else:
            user_part = user_part_without_name
        
        # 获取示例数据（从 example_templates 中获取所有示例）
        examples = self._get_examples_for_type(content_type)

        # 构建 prompt
        greet_name = {"good_m": "morning", "good_n": "evening", "good_l": "late at night", "good_w": "weekend"}

        if "commentary" == content_type:
            prompt = prompt_template.format(
                user_part=user_part,
                selected_style=selected_style,
                lang_policy=lang_policy,
                examples=examples
            )
        elif "good_m" == content_type or "good_n" == content_type:
            prompt = prompt_template.format(
                greet_type=greet_name[content_type],
                user_part=user_part,
                selected_style=selected_style,
                contexts=contexts,
                lang_policy=lang_policy,
                examples=examples
            )
        else:
            greet_type_str = f"festival: {festival_name}" if "good_f" == content_type else greet_name[content_type]
            prompt = prompt_template.format(
                greet_type = greet_type_str,
                user_part=user_part,
                selected_style=selected_style,
                lang_policy=lang_policy,
                examples=examples
            )
        
        logger.info(
            "Prompt构建成功",
            content_type=content_type,
            language_code=language_code,
            style=selected_style,
            has_user_name=bool(user_name),
            has_contexts=bool(contexts),
        )
        return prompt
    
    @staticmethod
    def _get_examples_for_type(content_type: str) -> str:
        """
        获取指定类型的所有示例
        
        Args:
            content_type: 内容类型
        
        Returns:
            str: 格式化的示例字符串
        """
        # 从 example_templates 获取英文示例
        en_examples = example_templates.get('en', {})
        examples_list = en_examples.get(content_type, [])
        
        if not examples_list:
            return "No examples available"
        
        # 将所有示例格式化为字符串
        formatted_examples = "\n".join([f"- {example}" for example in examples_list])
        return formatted_examples
    
    # def get_supported_languages(self) -> Dict[str, list]:
    #     """
    #     获取支持的语言列表
    #
    #     Returns:
    #         Dict[str, list]: {"morning": [...], "evening": [...]}
    #     """
    #     return {
    #         "morning": list(self.morning_prompts.keys()),
    #         "evening": list(self.evening_prompts.keys())
    #     }


# 全局实例
content_prompt_manager = ContentPromptManager()


async def generate_content(
    content_type: str,
    client: Optional[AsyncOpenAI] = None,
    festival_name: Optional[str] = None,
    language_code: Optional[str] = None,
    user_name: Optional[str] = None,
    generate_prompt: Optional[str] = None,
    contexts: Optional[str] = None,
    topic: Optional[str] = None
) -> Dict[str, any]:
    """
    使用 OpenAI 兼容 API 生成个性化内容（问候语或点评）

    Args:
        content_type: "good_m" (早安)/"good_n" (晚安)/"good_l" (深夜)/"good_w" (周末)/"good_f" (节日)/"commentary" (点评)
        client: AsyncOpenAI 客户端实例（可选）
        festival_name: 节日名称(仅"good_f"使用)
        language_code: 语言代码
        user_name: 用户名（可选）
        generate_prompt: 生成物提示词 (可选)
        contexts: 上下文 (可选)
        topic: 主题（可选）

    Returns:
        Dict: {"success": bool, "content": str, "error": str (可选), "fallback": bool}

    Examples:
        - result = await generate_content("good_m", "zh", "张三")
        - result["success"]
        - True
        - "content" in result
        - True
    """
    logger.info(
        "LLM内容生成开始",
        content_type=content_type,
        festival_name=festival_name,
        language_code=language_code,
        has_user_name=bool(user_name),
        has_contexts=bool(contexts),
        has_generate_prompt=bool(generate_prompt),
    )
    
    # 获取 prompt
    prompt_input = generate_prompt if "commentary" == content_type else contexts

    prompt = content_prompt_manager.get_prompt(content_type,
                                               festival_name,
                                               language_code=language_code,
                                               user_name=user_name,
                                               contexts=prompt_input)
    
    try:
        # 如果没有传入 client，创建一个
        if client is None:
            client = AsyncOpenAI(
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL
            )
        
        # 调用 LLM API
        completion = await client.chat.completions.create(
            model=GREET_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=LLM_TEMPERATURE,
            timeout=LLM_TIMEOUT
        )
        
        content = completion.choices[0].message.content.strip()
        content = content.strip('"\'""''，。！？.?!')
        
        # 字数/词数检查
        normalized_lang = normalize_language_code(language_code)
        if is_cjk_language(normalized_lang):  # CJK 语言按字符数
            if len(content) > MAX_GREETING_LENGTH_CJK:
                logger.warning(
                    "LLM生成内容过长降级处理",
                    content_type=content_type,
                    length=len(content),
                    content_preview=content[:50],
                    max_length=MAX_GREETING_LENGTH_CJK,
                    language=normalized_lang,
                )
                raise ValueError("生成内容过长, 降级使用模板内容")
        else:  # 其他语言按单词数
            word_count = len(content.split())
            if word_count > MAX_GREETING_LENGTH_EN:
                logger.warning(
                    "LLM生成内容过长降级处理",
                    content_type=content_type,
                    word_count=word_count,
                    content_preview=content[:100],
                    max_word_count=MAX_GREETING_LENGTH_EN,
                    language=normalized_lang,
                )
                raise ValueError("生成内容过长, 降级使用模板内容")
        
        logger.info(
            "LLM内容生成成功",
            content_type=content_type,
            language=normalized_lang,
            content=content,
        )
        return {
            "success": True,
            "greeting": content,  # 向后兼容
            "language": language_code,
            "fallback": False
        }

    except Exception as e:
        logger.error(
            "LLM内容生成失败",
            content_type=content_type,
            language_code=language_code,
            error=str(e),
            exc_info=True,
        )
        normalized_lang = normalize_language_code(language_code)
        fallback_content = get_fallback_content(content_type, normalized_lang, user_name)
        if "good_m" == content_type or "good_n" == content_type:
            fallback_content = fallback_content.format(topic=topic)
        logger.info(
            "LLM内容生成降级处理",
            language=normalized_lang,
            content=fallback_content,
        )
        return {
            "success": False,
            "greeting": fallback_content,  # 向后兼容
            "language": language_code,
            "error": f"LLM生成失败: {str(e)}",
            "fallback": True
        }


def get_fallback_content(
    content_type: str,
    language_code: str = "en",
    user_name: Optional[str] = None
) -> str:
    """
    备用内容模板
    
    Args:
        content_type: "good_m" (早安)/"good_n" (晚安)/"good_l" (深夜)/"good_w"(周末)/"good_f"(节日)/"commentary" (点评)"
        language_code: 标准化后的语言代码
        user_name: 用户名（可选）
    
    Returns:
        str: 备用内容
    
    Examples:
        - content = get_fallback_content("good_m", "zh", "张三")
        - len(content) > 0
        - True
    """ 
    
    # 获取对应语言的模板
    lang_templates = fallback_templates.get(language_code, fallback_templates["en"])
    contents = lang_templates.get(content_type, lang_templates["good_m"])
    
    content = random.choice(contents)
    
    # 添加用户名（70%概率）
    if user_name and random.random() < 0.7:
        if language_code == "zh":
            content = f"{user_name}，{content}"
        elif language_code == "ja":
            content = f"{user_name}さん、{content}"
        else:
            content = f"{user_name}, {content}"
    
    return content


async def gen_template_commentary(
        input_urls:list[str],
        output_url:str,
        language_code:str
) -> dict:
    pipe = PipelineV2()
    out = await pipe.run(
        user_upload_url=input_urls,
        s3_url=output_url,
        language_code=language_code,
        context="",
    )
    return out


async def gen_template_commentary_v2(
    input_urls:list[str],
    output_url:str,
    language_code:str
) -> dict:
    generated_type = "video" if is_video_url(output_url) else "image"
    try:
        result = await call_gemini_compare_and_comment(
            image_urls=input_urls,
            generated_url=output_url,
            generated_type=generated_type,
            timeout=LLM_TIMEOUT,
            language_code=language_code
        )
        return {
            "success": True,
            "greeting": result["comment"],
            "fallback": False
        }
    except Exception as e:
        logger.warning(e)
        return {
            "success": False,
            "greeting": None,
            "fallback": True
        }


# 保持向后兼容的别名
generate_greeting = generate_content
get_fallback_greeting = get_fallback_content
prompt_manager = content_prompt_manager
GreetingPromptManager = ContentPromptManager
