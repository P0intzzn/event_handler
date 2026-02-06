import httpx
import time
import random
from typing import List, Literal, Optional, Literal

import const
from utils.language_utils import is_cjk_language, normalize_language_code
from utils.logger import logger

ONEROUTER_URL = f"{const.OPENAI_BASE_URL}/chat/completions"


IMAGE_PROMPT = """
You are an assistant that reviews a GENERATED IMAGE using user-provided SOURCE IMAGES.

TYPE = IMAGE. This is a strict fact. Do not change it.

Inputs (order matters):
- The FIRST 1 or more image_url inputs = Source Images (user materials).
- The LAST image_url input = Generated Image (final result).

Rules:
- Treat all earlier images as source materials only.
- Treat the last image_url only as the generated result.
- Never treat the last image as a source image.
- Always treat the result as an IMAGE.

Internal steps (do not output):
1) Summarize Source Images: theme, subjects, setting, style.
2) Summarize Generated Image: subject, composition, lighting, color, key details.
3) Compare: subject link, theme link, style change, new elements.

Consistency check:
- MATCH = subject OR theme OR style is clearly connected.
- MISMATCH = subject AND theme are mostly unrelated.

Output ONE short message in {language_code}.

If MATCH:
- Be friendly and natural.
- Mention at least ONE of: composition, lighting, color, texture.
- Highlight 1 creative positive detail.
- No motion / pacing / transitions.
- {length_rule}
- End with a light question offering to help write 2–4 short captions for social sharing tied to a visual highlight.

If MISMATCH:
- Do NOT praise.
- Calm, non-judgmental tone.
- Briefly say what feels inconsistent (subject / theme / style).
- Say it looks fine on its own but diverges from the materials.
- Suggest ONE next step:
  * adjust the source images to better match the intended theme or subject
  * OR switch to a template that better fits the current materials
- End with a friendly question asking whether the user wants to tweak the materials or explore a more suitable template.

Generate now:
""".strip()

VIDEO_PROMPT = """
You are an assistant that reviews a GENERATED VIDEO using user-provided SOURCE IMAGES.

TYPE = VIDEO. This is a strict fact. Do not change it.

Inputs (order matters):
- The FIRST 1 or more image_url inputs = Source Images (user materials).
- The LAST video_url input = Generated Video (final result).

Rules:
- Treat all earlier images as source materials only.
- Treat the last video_url only as the generated result.
- Never treat the last item as a source image.
- Always treat the result as a VIDEO.

Internal steps (do not output):
1) Summarize Source Images: theme, subjects, setting, style.
2) Summarize Generated Video: subject, storyline, motion, pacing, transitions, visual style.
3) Compare: subject link, theme link, style change, new elements.

Consistency check:
- MATCH = subject OR theme OR style is clearly connected.
- MISMATCH = subject AND theme are mostly unrelated.

Output ONE short message in {language_code}.

If MATCH:
- Be friendly and natural.
- Mention at least ONE of: motion, pacing, transitions, rhythm, or music sync.
- Highlight 1 creative positive detail.
- No still-image wording.
- {length_rule}
- End with a light question offering to help write 2–4 short captions for social sharing tied to a visual or rhythm highlight.

If MISMATCH:
- Calm, non-judgmental tone.
- Briefly say what feels inconsistent (subject / theme / style).
- Say it looks fine on its own but diverges from the materials.
- Suggest ONE next step:
  * adjust the source images to better match the intended theme or subject
  * OR switch to a template that better fits the current materials
- End with a friendly question asking whether the user wants to tweak the materials or explore a more suitable template.

Generate now:
""".strip()


async def call_gemini_compare_and_comment(
    image_urls: List[str],
    generated_url: str,
    generated_type: str,
    timeout: float = 60.0,
    language_code: Optional[str] = "en",
):
    """
    调用 Gemini 模型对生成内容与素材进行对比并生成点评
    
    功能：
    - 接收 N 个素材图片和 1 个生成的图片/视频
    - 调用 OneRouter API 进行内容对比和点评生成
    - 自动拦截 OneRouter 的 fallback 文本
    - 返回最终可展示的点评文本
    
    参数：
    - image_urls: List[str] - 素材图片的 URL 列表（至少 1 张）
    - generated_url: str - 生成的图片或视频的 URL
    - generated_type: str - 生成内容的类型，必须是 'image' 或 'video'
    - timeout: float - 请求超时时间（秒），默认 60.0
    - language_code: Optional[str] - 生成点评的语言代码，默认 "en"
    
    返回值：
    - Dict[str, Any] - 包含以下字段的字典：
      - req_id: str - 请求 ID
      - model: str - 使用的模型名称
      - comment: str - 生成的点评文本
    
    异常：
    - ValueError - 参数验证失败
    - RuntimeError - API 请求失败或响应处理失败
    """
    # 记录函数调用信息
    logger.info(
        "call_gemini_compare_and_comment 函数调用开始",
        image_urls_count=len(image_urls),
        generated_url=generated_url,
        generated_type=generated_type,
        language_code=language_code
    )

    if not image_urls:
        raise ValueError("image_urls 不能为空（至少 1 张素材图片）")

    if generated_type not in ("image", "video"):
        raise ValueError("generated_type 必须是 'image' 或 'video'")

    req_id = f"{int(time.time()*1000)}-{random.randint(1000,9999)}"

    headers = {
        "Authorization": f"Bearer {const.OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "X-Request-ID": req_id,
    }

    # 1️⃣ 构造 multimodal content blocks
    content_blocks = []

    # 素材图片（N 张）
    for url in image_urls:
        content_blocks.append(
            {"type": "image_url", "image_url": {"url": url}}
        )

    # 生成结果（1 个：image 或 video）
    if generated_type == "image":
        content_blocks.append(
            {"type": "image_url", "image_url": {"url": generated_url}}
        )
        text_prompt = IMAGE_PROMPT
    else:
        content_blocks.append(
            {"type": "video_url", "video_url": {"url": generated_url}}
        )
        text_prompt = VIDEO_PROMPT

    # 文字指令（显式角色定义 + JSON 输出约束）
    normalize_lang_code = normalize_language_code(language_code)
    length_rule = (
        "Comments length: 50-80 Chinese characters"
        if is_cjk_language(normalize_lang_code)
        else "Comments length: 30-60 words"
    )
    prompt = text_prompt.format(length_rule=length_rule, language_code=normalize_lang_code)
    content_blocks.append(
        {"type": "text", "text": prompt}
    )
    logger.info(
        "文字指令内容块构造完成",
        language_code=normalize_lang_code
    )

    payload = {
        "model": const.DEFAULT_LLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": content_blocks,
            }
        ],
        "temperature": 0.4,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, limits=httpx.Limits(max_keepalive_connections=0)) as client:
            resp = await client.post(
                ONEROUTER_URL,
                headers=headers,
                json=payload,
            )
        logger.info(
            "HTTP 请求发送成功",
            status_code=resp.status_code
        )
    except httpx.ConnectError as e:
        logger.error(
            "HTTP 请求连接失败",
            error=str(e)
        )
        raise RuntimeError(f"[{req_id}] 连接失败: {e}")
    except httpx.TimeoutException as e:
        logger.error(
            "HTTP 请求超时",
            error=str(e)
        )
        raise RuntimeError(f"[{req_id}] 请求超时: {e}")
    except httpx.NetworkError as e:
        logger.error(
            "HTTP 请求网络错误",
            error=str(e)
        )
        raise RuntimeError(f"[{req_id}] 网络错误: {e}")
    except httpx.HTTPError as e:
        logger.error(
            "HTTP 请求错误",
            error=str(e)
        )
        raise RuntimeError(f"[{req_id}] HTTP错误: {e}")

    # 2️⃣ HTTP 级错误
    if resp.status_code != 200:
        logger.error(
            "OneRouter 返回非 200 状态码",
            status_code=resp.status_code,
            response_text=resp.text
        )
        raise RuntimeError(
            f"[{req_id}] OneRouter HTTP {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    logger.info("响应数据解析完成")

    # 4️⃣ OneRouter 级错误
    if "error" in data:
        logger.error(
            "OneRouter 返回错误信息",
            error=data["error"]
        )
        raise RuntimeError(f"[{req_id}] OneRouter error: {data['error']}")

    # 5️⃣ 正常内容提取
    try:
        msg = data["choices"][0]["message"]["content"]
        logger.info(
            "成功提取模型响应内容",
        )
    except Exception:
        logger.error(
            "模型响应结构无效",
            response_data=data
        )
        raise RuntimeError(f"[{req_id}] Invalid response schema: {data}")

    # 6️⃣ 识别 OneRouter fallback 模板文本
    if isinstance(msg, str) and any(
        msg.startswith(p) for p in (
            "The generated result is",
            "The model produced an error",
            "I'm sorry",
            "I cannot",
        )
    ):
        logger.warning(
            "OneRouter fallback 模板文本命中",
            fallback_text=msg[:120]
        )
        raise RuntimeError(f"[{req_id}] OneRouter fallback text hit: {msg[:120]}")


    # 7️⃣ 最终输出清洗（去掉偶发引号 / 多余空白）
    if not isinstance(msg, str) or not msg.strip():
        logger.error(
            "模型输出为空或无效"
        )
        raise RuntimeError(f"[{req_id}] Empty model output")

    final_comment = msg.strip().strip('"').strip()
    logger.info(
        "call_gemini_compare_and_comment 函数调用完成",
        final_comment_length=len(final_comment)
    )

    return {
        "req_id": req_id,
        "model": const.DEFAULT_LLM_MODEL,
        "comment": final_comment,
    }
