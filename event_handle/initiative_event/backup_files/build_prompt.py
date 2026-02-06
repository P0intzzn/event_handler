# build_prompt.py
from __future__ import annotations

import json
import random
from pathlib import Path
from functools import lru_cache
from typing import Optional, Tuple, Dict, Any

PROMPT_DIR = Path("prompts")  # 你也可以改成绝对路径 or 从 env 读取


def resolve_lang_zh_en(language_code: Optional[str]) -> str:
    """当前阶段：中文归为 zh，其余全部归为 en；默认 zh。"""
    if not language_code:
        return "zh"
    code = language_code.strip().replace("_", "-").lower()
    return "zh" if code.startswith("zh") else "en"


@lru_cache(maxsize=16)
def load_prompt_cfg(greet_type: str) -> Dict[str, Any]:
    """
    读取 prompts/morning_prompts.json 或 prompts/evening_prompts.json
    文件结构示例:
    {
      "zh": { "styles": [...], "prompts": "...", "examples": [...], "postprocess": {...}, "language_name": "中文" },
      "en": { ... }
    }
    """
    path = PROMPT_DIR / f"{greet_type}.json"
    if not path.exists():
        raise FileNotFoundError(f"Prompt config not found: {path.resolve()}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_user_part(lang_key: str, user_name: Optional[str]) -> str:
    if lang_key == "zh":
        return f"用户叫{user_name}。" if user_name else "不需要称呼单个用户；请面向群聊，使用：大家/各位/你们。"
    else:
        return f"User's name is {user_name}. " if user_name else "Don't use user's name. Address the group (everyone/folks). "


def format_examples(examples_list, k_choices=(1, 2)) -> str:
    if not examples_list:
        return "- (no examples)"
    k = min(random.choice(k_choices), len(examples_list))
    picked = random.sample(examples_list, k=k)
    return "\n".join([f"- {x}" for x in picked])


def build_greet_prompt(
    greet_type: str,
    language_code: Optional[str] = None,
    user_name: Optional[str] = None
) -> Tuple[str, str, str, str, Dict[str, Any]]:
    """
    返回:
      prompt: str
      selected_style: str
      language_name: str   # "中文"/"English"
      lang_key: str        # "zh"/"en" (当前阶段)
      lang_cfg: dict       # 该语言块配置（含 postprocess 等）
    """
    lang_key = resolve_lang_zh_en(language_code)

    all_cfg = load_prompt_cfg(greet_type)
    lang_cfg = all_cfg.get(lang_key) or all_cfg.get("en")
    if not lang_cfg:
        raise ValueError(f"Missing language config for {lang_key} and no en fallback")

    language_name = lang_cfg.get("language_name", "中文" if lang_key == "zh" else "English")

    styles = lang_cfg.get("styles", [])
    selected_style = random.choice(styles) if styles else "default"

    template = lang_cfg["prompts"]
    examples_text = format_examples(lang_cfg.get("examples", []))
    user_part = build_user_part(lang_key, user_name)

    prompt = template.format(
        user_part=user_part,
        selected_style=selected_style,
        examples=examples_text
    )

    return prompt, selected_style, language_name, lang_key, lang_cfg
