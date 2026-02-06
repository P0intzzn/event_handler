import json
import random
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# 获取 prompts 目录路径
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class GreetingPromptManager:
    """问候语 Prompt 管理器"""

    def __init__(self):
        self.morning_prompts = self._load_prompts("morning_prompts.json")
        self.evening_prompts = self._load_prompts("evening_prompts.json")
        logger.info(
            f"[PromptManager] 初始化完成 - 早安语言数: {len(self.morning_prompts)}, 晚安语言数: {len(self.evening_prompts)}")

    def _load_prompts(self, filename: str) -> Dict[str, dict]:
        """加载 prompt 配置文件"""
        file_path = PROMPTS_DIR / filename
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"[PromptManager] 加载成功 - {filename}")
                return data
        except FileNotFoundError:
            logger.error(f"[PromptManager] 文件不存在 - {file_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"[PromptManager] JSON解析失败 - {filename}, error: {e}")
            return {}

    def get_prompt(self, greet_type: str, language_code: Optional[str], user_name: Optional[str] = None) -> Optional[
        str]:
        """
        获取指定语言的 prompt

        Args:
            greet_type: "good_m" (早安) 或 "good_n" (晚安)
            language_code: 语言代码，如 "zh", "en", "ja" 等
            user_name: 用户名（可选）

        Returns:
            构建好的 prompt 字符串，如果语言不支持则返回 None
        """
        # 选择对应的 prompts 字典
        prompts_dict = self.morning_prompts if greet_type == "good_m" else self.evening_prompts

        # 语言代码标准化和映射
        lang_code = self._normalize_language_code(language_code)

        # 获取该语言的配置
        lang_config = prompts_dict.get(lang_code)
        if not lang_config:
            logger.warning(f"[PromptManager] 不支持的语言 - language_code: {language_code} (normalized: {lang_code})")
            return None

        # 随机选择一个风格
        styles = lang_config.get("styles", [])
        if not styles:
            logger.error(f"[PromptManager] 配置错误 - {lang_code} 无可用风格")
            return None

        selected_style = random.choice(styles)

        # 构建 prompt
        prompt_template = lang_config.get("template", "")
        if not prompt_template:
            logger.error(f"[PromptManager] 配置错误 - {lang_code} 缺少 template")
            return None

        # 替换模板变量
        user_part = lang_config.get("user_part_with_name", "").format(
            user_name=user_name) if user_name else lang_config.get("user_part_without_name", "")

        prompt = prompt_template.format(
            user_part=user_part,
            selected_style=selected_style
        )

        logger.debug(
            f"[PromptManager] Prompt构建成功 - greet_type: {greet_type}, language: {lang_code}, style: {selected_style}")
        return prompt

    def _normalize_language_code(self, language_code: Optional[str]) -> str:
        """
        标准化语言代码
        将各种变体映射到统一的语言代码
        """
        if not language_code:
            return "zh"  # 默认中文

        # 转小写处理
        lang = language_code.lower()

        # 中文变体映射
        chinese_variants = ["zh", "zh-cn", "zh-hans", "zh-tw", "zh-hant"]
        if lang in chinese_variants:
            return "zh"

        # 英文变体映射
        english_variants = ["en", "en-us", "en-gb"]
        if lang in english_variants:
            return "en"

        # 日文变体映射
        japanese_variants = ["ja", "ja-jp"]
        if lang in japanese_variants:
            return "ja"

        # 韩文变体映射
        korean_variants = ["ko", "ko-kr"]
        if lang in korean_variants:
            return "ko"

        # 其他语言直接返回前两位
        return lang[:2] if len(lang) >= 2 else lang

    def get_supported_languages(self) -> Dict[str, list]:
        """获取支持的语言列表"""
        return {
            "morning": list(self.morning_prompts.keys()),
            "evening": list(self.evening_prompts.keys())
        }


# 全局实例
prompt_manager = GreetingPromptManager()


async def generate_greeting(greet_type: str, language_code: Optional[str] = None,
                            user_name: Optional[str] = None, client=None) -> dict:
    """
    使用 OpenAI 兼容 API 生成个性化问候语

    Args:
        greet_type: "good_m" (早安) 或 "good_n" (晚安)
        language_code: 语言代码
        user_name: 用户名（可选）
        client: AsyncOpenAI 客户端实例

    Returns:
        {"success": bool, "greeting": str, "error": str (可选), "fallback": bool}
    """
    logger.info(
        f"[LLM生成] 开始生成问候语 - greet_type: {greet_type}, language_code: {language_code}, user_name: {user_name}")

    # 获取 prompt
    prompt = prompt_manager.get_prompt(greet_type, language_code, user_name)

    if not prompt:
        # 语言不支持，使用备用方案
        normalized_lang = prompt_manager._normalize_language_code(language_code)
        logger.warning(
            f"[LLM生成] 语言不支持，使用备用方案 - language_code: {language_code} (normalized: {normalized_lang})")
        fallback_greeting = get_fallback_greeting(greet_type, normalized_lang, user_name)
        return {
            "success": False,
            "greeting": fallback_greeting,
            "language": normalized_lang,
            "error": f"不支持的语言: {language_code}",
            "fallback": True
        }

    try:
        # 调用 LLM API
        import os
        completion = await client.chat.completions.create(
            model=os.getenv("LLM_GREET_MODEL") or "gemini-2.5-flash",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.2,
            timeout=15.0
        )

        greeting = completion.choices[0].message.content.strip()
        greeting = greeting.strip('"\'""''，。！？.?!')

        # 字数/词数检查
        normalized_lang = prompt_manager._normalize_language_code(language_code)
        if normalized_lang in ["zh", "ja", "ko"]:  # CJK 语言按字符数
            max_length = 35
            if len(greeting) > max_length:
                logger.warning(f"[LLM生成] 内容过长({len(greeting)}字)，截断处理")
                greeting = greeting[:30] + "..."
        else:  # 其他语言按单词数
            word_count = len(greeting.split())
            if word_count > 25:
                logger.warning(f"[LLM生成] 内容过长({word_count}词)，截断处理")
                greeting = " ".join(greeting.split()[:20]) + "..."

        logger.info(f"[LLM生成] 生成成功 - language: {normalized_lang}, length: {len(greeting)}")
        return {
            "success": True,
            "greeting": greeting,
            "language": normalized_lang,
            "fallback": False
        }

    except Exception as e:
        logger.error(f"[LLM生成] 生成失败 - error: {str(e)}", exc_info=True)
        normalized_lang = prompt_manager._normalize_language_code(language_code)
        fallback_greeting = get_fallback_greeting(greet_type, normalized_lang, user_name)
        return {
            "success": False,
            "greeting": fallback_greeting,
            "language": normalized_lang,
            "error": f"LLM生成失败: {str(e)}",
            "fallback": True
        }


def get_fallback_greeting(greet_type: str, language_code: str = "zh", user_name: Optional[str] = None) -> str:
    """
    备用问候语模板

    Args:
        greet_type: "good_m" 或 "good_n"
        language_code: 标准化后的语言代码
        user_name: 用户名（可选）
    """
    # 备用模板字典
    fallback_templates = {
        "zh": {
            "good_m": [
                "早安！新的一天开始了",
                "早上好，今天也要加油",
                "晨光正好，不负韶华",
                "元气满满迎接新一天"
            ],
            "good_n": [
                "晚安，做个好梦",
                "夜深了，好好休息",
                "夜色温柔，愿你安眠",
                "今日已尽，明日可期"
            ]
        },
        "en": {
            "good_m": [
                "Good morning! Have a great day",
                "Morning! Hope you have a wonderful day",
                "Rise and shine! New day awaits",
                "Good morning! Let's make today amazing"
            ],
            "good_n": [
                "Good evening! Rest well tonight",
                "Evening! Hope you had a good day",
                "Stars shine bright, sleep tight",
                "Good night! Dream sweet dreams"
            ]
        },
        "ja": {
            "good_m": [
                "おはようございます！素敵な一日を",
                "朝ですよ！今日も頑張りましょう",
                "おはよう！良い一日になりますように"
            ],
            "good_n": [
                "お疲れ様でした、おやすみなさい",
                "良い夢を見てください",
                "今日も一日お疲れ様、ゆっくり休んでね"
            ]
        }
    }

    # 获取对应语言的模板
    lang_templates = fallback_templates.get(language_code, fallback_templates["en"])
    greetings = lang_templates.get(greet_type, lang_templates["good_m"])

    greeting = random.choice(greetings)

    # 添加用户名（70%概率）
    if user_name and random.random() < 0.7:
        if language_code == "zh":
            greeting = f"{user_name}，{greeting}"
        elif language_code == "ja":
            greeting = f"{user_name}さん、{greeting}"
        else:
            greeting = f"{user_name}, {greeting}"

    return greeting