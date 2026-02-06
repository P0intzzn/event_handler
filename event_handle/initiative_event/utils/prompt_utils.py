"""
Prompt 构建与管理工具模块

提供 Prompt 配置加载、构建等功能
"""
import json
import random
from pathlib import Path
from functools import lru_cache
from typing import Optional, Dict, Any

from const import PROMPTS_DIR


@lru_cache(maxsize=16)
def load_prompt_config(filename: str) -> Dict[str, Any]:
    """
    加载 Prompt 配置文件
    
    Args:
        filename: 配置文件名（如 "morning_prompts.json"）
    
    Returns:
        Dict[str, Any]: 配置字典
    
    Raises:
        FileNotFoundError: 配置文件不存在
        json.JSONDecodeError: JSON 解析失败
    
    Examples:
        - config = load_prompt_config("morning_prompts.json")
        - "zh" in config
        True
    """
    file_path = PROMPTS_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Prompt 配置文件不存在: {file_path}")
    
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_user_part(language_code: str, user_name: Optional[str]) -> str:
    """
    构建用户称呼部分的 Prompt
    
    Args:
        language_code: 语言代码（zh, en 等）
        user_name: 用户名（可选）
    
    Returns:
        str: 用户称呼部分的 Prompt
    
    Examples:
        - build_user_part("zh", "张三")
        '用户叫张三。'
        - build_user_part("zh", None)
        '不需要称呼单个用户；请面向群聊，使用：大家/各位/你们。'
    """
    if language_code == "zh":
        return f"用户叫{user_name}。" if user_name else "不需要称呼单个用户；请面向群聊，使用：大家/各位/你们。"
    else:
        return f"User's name is {user_name}. " if user_name else "Don't use user's name. Address the group (everyone/folks). "


def format_examples(examples_list: list[str], k_choices: tuple[int, int] = (1, 2)) -> str:
    """
    格式化示例列表
    
    Args:
        examples_list: 示例列表
        k_choices: 随机选择的示例数量范围
    
    Returns:
        str: 格式化后的示例文本
    
    Examples:
        - examples = ["示例1", "示例2", "示例3"]
        - result = format_examples(examples)
        - "- " in result
        True
    """
    if not examples_list:
        return "- (no examples)"
    
    k = min(random.choice(k_choices), len(examples_list))
    picked = random.sample(examples_list, k=k)
    return "\n".join([f"- {x}" for x in picked])


def build_greet_prompt(
    greet_type: str,
    language_code: Optional[str] = None,
    user_name: Optional[str] = None
) -> tuple[str, str, str, str, Dict[str, Any]]:
    """
    构建问候语 Prompt
    
    Args:
        greet_type: 问候类型（如 "good_m", "good_n"）
        language_code: 语言代码
        user_name: 用户名（可选）
    
    Returns:
        tuple: (prompt, selected_style, language_name, lang_key, lang_cfg)
            - prompt: 构建好的 Prompt 字符串
            - selected_style: 随机选择的风格
            - language_name: 语言名称（如 "中文", "English"）
            - lang_key: 标准化后的语言代码（zh, en）
            - lang_cfg: 该语言的完整配置
    
    Raises:
        ValueError: 语言配置缺失
    
    Examples:
        - prompt, style, lang_name, lang_key, cfg = build_greet_prompt("good_m", "zh", "张三")
        - lang_key
        'zh'
        - "张三" in prompt
        True
    """
    from utils.language_utils import normalize_language_code
    
    lang_key = normalize_language_code(language_code)
    
    # 构建配置文件名（根据 greet_type）
    if greet_type == "good_m":
        config_file = "morning_prompts.json"
    elif greet_type == "good_n":
        config_file = "evening_prompts.json"
    else:
        raise ValueError(f"不支持的问候类型: {greet_type}")
    
    all_cfg = load_prompt_config(config_file)
    lang_cfg = all_cfg.get(lang_key) or all_cfg.get("en")
    
    if not lang_cfg:
        raise ValueError(f"缺少语言配置: {lang_key}，且无 en 备选")
    
    language_name = lang_cfg.get("language_name", "中文" if lang_key == "zh" else "English")
    
    styles = lang_cfg.get("styles", [])
    selected_style = random.choice(styles) if styles else "default"
    
    template = lang_cfg.get("template", "")
    if not template:
        raise ValueError(f"语言配置 {lang_key} 缺少 template 字段")
    
    # 构建用户部分
    user_part_with_name = lang_cfg.get("user_part_with_name", "")
    user_part_without_name = lang_cfg.get("user_part_without_name", "")
    
    if user_name and user_part_with_name:
        user_part = user_part_with_name.format(user_name=user_name)
    else:
        user_part = user_part_without_name
    
    # 构建 prompt
    prompt = template.format(
        user_part=user_part,
        selected_style=selected_style
    )
    
    return prompt, selected_style, language_name, lang_key, lang_cfg
