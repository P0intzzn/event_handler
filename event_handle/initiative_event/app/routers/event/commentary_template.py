"""
Agnes Pipeline V2 (Integrated, Runnable)
- User uploads (1..N) analyzed in parallel (bounded concurrency)
- Generated result (s3/http/local) analyzed in parallel with user batch
- Blocking I/O (requests/boto3/downloads) moved off event-loop via asyncio.to_thread
- API key MUST come from env: LLM_API_KEY (no hardcoding)
"""

import os
import re
import json
import base64
import mimetypes
import tempfile
import logging
import time
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List
from urllib.parse import urlparse

import boto3
import requests
from bs4 import BeautifulSoup
from openai import AsyncOpenAI

import const
from utils.logger import logger

# ============================================================
# Config
# ============================================================

@dataclass(frozen=True)
class AppConfig:
    # ✅ Use env; NEVER hardcode keys in code
    api_key: str = const.OPENAI_API_KEY
    base_url: str = const.OPENAI_BASE_URL
    analyze_model: str = const.DEFAULT_LLM_MODEL
    comment_model: str = const.DEFAULT_LLM_MODEL

    llm_timeout: float = const.LLM_TIMEOUT
    http_timeout: float = const.HTTP_TIMEOUT

    max_download_bytes: int = int(os.getenv("MAX_DOWNLOAD_BYTES", str(200 * 1024 * 1024)))  # 200MB

    # ✅ user uploads batch limit
    max_user_items: int = int(os.getenv("MAX_USER_ITEMS", "3"))

    # ✅ concurrency bound (downloads/decoding/llm)
    analyze_concurrency: int = int(os.getenv("ANALYZE_CONCURRENCY", "3"))

    # optional: PDF vision (scanned pdf / charts)
    enable_pdf_vision: bool = os.getenv("ENABLE_PDF_VISION", "0").strip().lower() in ("1", "true", "yes")
    pdf_vision_pages: int = int(os.getenv("PDF_VISION_PAGES", "2"))

    # video frame sampling by relative time
    video_time_points: Tuple[float, ...] = (0.0, 0.5, 0.9)

    # greeting retries (length enforcement)
    comment_retries: int = int(os.getenv("COMMENT_RETRIES", "2"))


# ============================================================
# Small utils
# ============================================================

def _clean_quotes_punct(s: str) -> str:
    """
    清理字符串中的引号和标点符号
    
    Args:
        s: 待清理的字符串
        
    Returns:
        清理后的字符串，移除了首尾的引号和标点符号
        
    Notes:
        移除的符号包括: " ' “ ” ‘ ’ ， 。 ！ ？ . ? ! \n \t
    """
    if not s:
        return ""
    return s.strip().strip('"\'“”‘’，。！？.?! \n\t')


def _word_count_en(s: str) -> int:
    """
    计算英文单词数
    
    Args:
        s: 待计数的英文字符串
        
    Returns:
        字符串中的单词数量
        
    Notes:
        使用正则表达式按空白字符分割，统计非空单词数量
    """
    return len([w for w in re.split(r"\s+", s.strip()) if w])


def _safe_preview(text: str, limit: int = 1200) -> str:
    """
    生成安全的文本预览
    
    Args:
        text: 原始文本
        limit: 预览长度限制，默认1200字符
        
    Returns:
        处理后的预览文本
        
    Notes:
        - 移除回车符
        - 将连续的换行符压缩为最多两个
        - 截断到指定长度
    """
    if not text:
        return ""
    t = text.replace("\r", "")
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t[:limit]


def _b64_of_bytes(b: bytes) -> str:
    """
    将字节数据转换为Base64编码字符串
    
    Args:
        b: 待编码的字节数据
        
    Returns:
        Base64编码的UTF-8字符串
    """
    return base64.b64encode(b).decode("utf-8")


def _b64_of_file(path: str) -> str:
    """
    读取文件并转换为Base64编码字符串
    
    Args:
        path: 文件路径
        
    Returns:
        文件内容的Base64编码字符串
        
    Raises:
        FileNotFoundError: 文件不存在
        IOError: 文件读取失败
    """
    with open(path, "rb") as f:
        return _b64_of_bytes(f.read())


def _infer_type_from_url(url: str) -> str:
    """
    Heuristic:
    - based on suffix when available
    - treat html-like urls as web_url
    """
    if not url:
        return "txt"

    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lower()

    # web pages
    if url.startswith(("http://", "https://")):
        if suffix in {"", ".html", ".htm"}:
            return "web_url"

    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
        return "image"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".mp4", ".mov", ".avi", ".mkv", ".flv"}:
        return "video"
    if suffix in {".docx"}:
        return "docx"
    if suffix in {".txt", ".md", ".log", ".json"}:
        return "txt"

    # fallback
    return "txt"


def _language_name_for_prompt(lang: str) -> str:
    """
    将语言代码转换为语言名称，用于Prompt构建
    
    Args:
        lang: 语言代码（如 "en", "zh", "ja" 等）
        
    Returns:
        语言名称（如 "English", "Chinese", "Japanese" 等）
        如果语言代码不在映射表中，默认返回 "English"
        
    Notes:
        支持的语言包括：英语、中文（简体/繁体）、印尼语、泰语、
        他加禄语、菲律宾语、马来语、越南语、西班牙语、葡萄牙语、法语、日语、韩语
    """
    return {
        "en": "English",
        "zh-CN": "Chinese (Simplified, China)",
        "zh": "Chinese",
        "zh-Hans": "Chinese (Simplified)",
        "id": "Indonesian",
        "th": "Thai",
        "tl": "Tagalog",
        "fil": "Filipino",
        "ms": "Malay",
        "vi": "Vietnamese",
        "es": "Spanish",
        "pt": "Portuguese",
        "fr": "French",
        "ja": "Japanese",
        "ko": "Korean",
        "Nihongo": "Japanese",
        "Hangugeo": "Korean",
    }.get(lang, "English")


def _is_zh(lang: str) -> bool:
    """
    判断是否为中文语言代码
    
    Args:
        lang: 语言代码
        
    Returns:
        如果是中文语言代码返回True，否则返回False
        
    Notes:
        支持的中文语言代码包括：
        - zh: 中文通用
        - zh-CN: 简体中文（中国）
        - zh-Hans: 简体中文
        - zh-Hant: 繁体中文
        - zh-TW: 繁体中文（台湾）
        - zh-HK: 繁体中文（香港）
    """
    return lang in {"zh", "zh-CN", "zh-Hans", "zh-Hant", "zh-TW", "zh-HK"}


# ============================================================
# Localizer: treat input url as s3://... or http(s)://... or local
# ============================================================

class Localizer:
    """
    文件本地化类 - 将远程文件下载到本地
    
    支持多种文件来源：
    - S3存储（s3://）
    - HTTP/HTTPS URL
    - 本地文件路径
    
    Attributes:
        cfg: 应用配置对象
        s3: boto3 S3客户端实例
    """
    
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.s3 = boto3.client("s3")

    def _download_http_to_temp(self, url: str, suffix: str) -> str:
        """
        从HTTP/HTTPS URL下载文件到临时目录
        
        Args:
            url: HTTP/HTTPS URL
            suffix: 文件后缀名（如 ".jpg", ".pdf"）
            
        Returns:
            临时文件的本地路径
            
        Raises:
            ValueError: 文件大小超过限制
            requests.exceptions.RequestException: HTTP请求失败
            
        Notes:
            - 使用流式下载以支持大文件
            - 下载过程中会检查文件大小限制
            - 失败时会自动清理临时文件
        """
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp_path = tmp.name
        tmp.close()

        total = 0
        logger.info(f"[Localizer][HTTP] downloading -> {tmp_path} | url={url}")
        try:
            with requests.get(url, timeout=self.cfg.http_timeout, stream=True) as r:
                r.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(1024 * 64):
                        if not chunk:
                            continue
                        total += len(chunk)
                        # 检查文件大小是否超过限制
                        if total > self.cfg.max_download_bytes:
                            raise ValueError(f"File too large (> {self.cfg.max_download_bytes} bytes): {url}")
                        f.write(chunk)

            logger.info(f"[Localizer][HTTP] done | bytes={total} | path={tmp_path}")
            return tmp_path
        except Exception as e:
            logger.warning(f"[Localizer][HTTP] failed | url={url} | err={type(e).__name__}: {e}")
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                logger.debug(f"[Localizer][HTTP] cleaned temp file: {tmp_path}")
            raise

    def _download_s3_to_temp(self, s3_uri: str, suffix: str) -> str:
        """
        从S3下载文件到临时目录
        
        Args:
            s3_uri: S3 URI（格式：s3://bucket/key）
            suffix: 文件后缀名
            
        Returns:
            临时文件的本地路径
            
        Raises:
            ValueError: S3 URI格式无效或文件大小超过限制
            botocore.exceptions.ClientError: S3下载失败
            
        Notes:
            - 解析S3 URI获取bucket和key
            - 下载后检查文件大小限制
            - 失败时会自动清理临时文件
        """
        u = urlparse(s3_uri)
        bucket = u.netloc
        key = u.path.lstrip("/")
        if not bucket or not key:
            raise ValueError(f"Invalid S3 URI: {s3_uri}")

        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp_path = tmp.name
        tmp.close()

        logger.info(f"[Localizer][S3] downloading -> {tmp_path} | s3={s3_uri}")
        try:
            self.s3.download_file(bucket, key, tmp_path)
            size = os.path.getsize(tmp_path)
            # 检查文件大小是否超过限制
            if size > self.cfg.max_download_bytes:
                raise ValueError(f"S3 file too large (> {self.cfg.max_download_bytes} bytes): {s3_uri}")
            logger.info(f"[Localizer][S3] done | bytes={size} | path={tmp_path}")
            return tmp_path
        except Exception as e:
            logger.warning(f"[Localizer][S3] failed | s3={s3_uri} | err={type(e).__name__}: {e}")
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                logger.debug(f"[Localizer][S3] cleaned temp file: {tmp_path}")
            raise

    def ensure_local(self, url: str, suffix: str) -> Tuple[str, bool]:
        """
        确保文件在本地可用，必要时下载
        
        Args:
            url: 文件URL或本地路径
            suffix: 文件后缀名（用于下载时）
            
        Returns:
            Tuple[str, bool]: (本地文件路径, 是否需要清理)
            - 需要清理标志：True表示是下载的临时文件，False表示是本地文件
            
        Raises:
            FileNotFoundError: 本地文件不存在
            ValueError: URL格式无效
            Exception: 下载失败
            
        Notes:
            - S3 URL: 下载到临时文件
            - HTTP/HTTPS URL: 下载到临时文件
            - 本地路径: 直接使用，不复制
        """
        if url.startswith("s3://"):
            return self._download_s3_to_temp(url, suffix), True

        if url.startswith(("http://", "https://")):
            return self._download_http_to_temp(url, suffix), True

        p = Path(url).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Not found: {p}")
        logger.info(f"[Localizer][LOCAL] use local path | path={p}")
        return str(p), False

    async def ensure_local_async(self, url: str, suffix: str) -> Tuple[str, bool]:
        """
        异步确保文件在本地可用
        
        Args:
            url: 文件URL或本地路径
            suffix: 文件后缀名
            
        Returns:
            Tuple[str, bool]: (本地文件路径, 是否需要清理)
            
        Notes:
            使用asyncio.to_thread将阻塞的下载操作移出事件循环
        """
        return await asyncio.to_thread(self.ensure_local, url, suffix)


# ============================================================
# LLM Client
# ============================================================

class LLMClient:
    """
    LLM客户端类 - 封装OpenAI兼容的异步API调用
    
    Attributes:
        cfg: 应用配置对象
        client: AsyncOpenAI客户端实例
        
    Notes:
        - 支持多模态内容（文本、图片等）
        - 使用异步调用，避免阻塞事件循环
        - 自动记录请求和响应日志
    """
    
    def __init__(self, cfg: AppConfig):
        if not cfg.api_key:
            raise RuntimeError("Missing env: LLM_API_KEY (do NOT hardcode keys)")
        self.cfg = cfg
        self.client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

    async def chat(self, model: str, content: List[Dict[str, Any]], temperature: float) -> str:
        """
        调用LLM API进行对话
        
        Args:
            model: 模型名称（如 "gpt-4", "claude-3" 等）
            content: 内容列表，支持多模态（文本、图片等）
                每个元素是字典，包含 "type" 和对应的内容
                例如：[{"type": "text", "text": "hello"}, {"type": "image_url", "image_url": {...}}]
            temperature: 温度参数，控制生成随机性（0.0-2.0）
                - 0.0: 更确定、保守
                - 1.0: 平衡
                - 2.0: 更随机、创造性
                
        Returns:
            LLM返回的文本内容（已去除首尾空白）
            
        Raises:
            Exception: API调用失败
            
        Notes:
            - 记录请求和响应的详细信息
            - 计算并记录请求耗时
            - 使用配置的超时时间
        """
        t0 = time.time()
        parts = [c.get("type", "?") for c in content]
        logger.info(f"[LLM] request | model={model} | temp={temperature} | parts={parts}")

        try:
            resp = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                temperature=temperature,
                timeout=self.cfg.llm_timeout,
            )
            out = (resp.choices[0].message.content or "").strip()
            dt = (time.time() - t0) * 1000
            logger.info(f"[LLM] response | model={model} | ms={dt:.0f} | preview={out[:200]!r}")
            return out
        except Exception as e:
            dt = (time.time() - t0) * 1000
            logger.warning(f"[LLM] failed | model={model} | ms={dt:.0f} | err={type(e).__name__}: {e}")
            raise


# ============================================================
# Analyzer prompts + JSON parsing
# ============================================================

def _build_analyze_prompt() -> str:
    """
    构建内容分析的Prompt
    
    Returns:
        分析任务的Prompt字符串
        
    Notes:
        - 要求LLM理解内容并识别主要语言
        - 返回JSON格式：{"language": "...", "analysis": "..."}
        - language使用ISO639-1或BCP47格式（如en/zh/ja）
        - analysis为简洁的描述或摘要
    """
    return (
        "You are a multimodal content understanding assistant.\n"
        "Task:\n"
        "1) Understand the content.\n"
        "2) Identify the primary language used in the content.\n\n"
        "Return STRICT JSON only (no markdown, no extra text):\n"
        "{\"language\": \"<ISO639-1 or BCP47 like en/zh/ja... or unknown>\", "
        "\"analysis\": \"<concise description/summary>\"}\n\n"
        "Notes:\n"
        "- If the content is mostly non-verbal or language cannot be determined, use \"unknown\".\n"
        "- Keep analysis concise but informative.\n"
    )


def _build_user_bundle_prompt() -> str:
    """
    构建用户材料汇总的Prompt
    
    Returns:
        汇总任务的Prompt字符串
        
    Notes:
        - 将多个用户上传材料的分析汇总为一个简洁的参考
        - 返回JSON格式：{"language": "...", "reference": "..."}
        - 如果语言不同，选择主要语言
    """
    return (
        "You are a content summarization assistant.\n"
        "Given multiple analyses of user-uploaded materials, summarize them into ONE concise reference.\n\n"
        "Return STRICT JSON only:\n"
        "{\"language\":\"<en/zh/.../unknown>\",\"reference\":\"<unified concise reference summary>\"}\n\n"
        "Notes:\n"
        "- Keep it short and representative.\n"
        "- If languages differ, choose the primary language.\n"
    )


def _build_diff_prompt(user_ref: str, gen_ref: str) -> str:
    """
    构建对比分析的Prompt
    
    Args:
        user_ref: 用户上传材料的参考描述
        gen_ref: 生成结果的参考描述
        
    Returns:
        对比任务的Prompt字符串
        
    Notes:
        - 比较用户上传和生成结果的差异
        - 返回JSON格式，包含：language, summary, differences, improvements, issues, suggestions
        - differences最多返回3个关键差异
    """
    return (
        "You are a comparison assistant.\n"
        "Compare USER_REFERENCE vs GENERATED_RESULT.\n"
        "Return STRICT JSON only:\n"
        "{\"language\":\"<en/zh/.../unknown>\","
        "\"summary\":\"<one-sentence overall comparison>\","
        "\"differences\":[\"<key diff 1>\",\"<key diff 2>\",\"<key diff 3>\"],"
        "\"improvements\":[\"<what is better in generated>\"] ,"
        "\"issues\":[\"<what is worse or missing>\"] ,"
        "\"suggestions\":\"<one short suggestion>\"}\n\n"
        f"USER_REFERENCE:\n{user_ref}\n\n"
        f"GENERATED_RESULT:\n{gen_ref}\n"
    )


def _parse_json_strict(text: str) -> Optional[Dict[str, Any]]:
    """
    严格解析JSON字符串，支持从混合文本中提取JSON
    
    Args:
        text: 可能包含JSON的字符串
        
    Returns:
        解析成功的JSON字典，失败返回None
        
    Notes:
        - 首先尝试直接解析整个字符串
        - 如果失败，尝试使用正则表达式提取第一个JSON对象
        - 使用DOTALL标志使.匹配换行符
        - 常用于从LLM返回的混合文本中提取JSON
    """
    if not text:
        return None
    t = text.strip()

    try:
        return json.loads(t)
    except Exception:
        pass

    # 尝试从文本中提取JSON对象
    m = re.search(r"\{.*\}", t, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# ============================================================
# ContentAnalyzer: url -> {language, analysis}
# ============================================================

class ContentAnalyzer:
    """
    多模态内容分析器 - 分析各种类型的文件内容
    
    支持的文件类型：
    - 图片（image）: JPG, PNG, WebP, GIF, BMP
    - 视频（video）: MP4, MOV, AVI, MKV, FLV
    - PDF文档（pdf）: 支持OCR视觉模式或文本提取
    - Word文档（docx）: 提取文本内容
    - 网页（web_url）: 提取网页文本
    - 纯文本（txt）: 直接读取文本
    
    Attributes:
        cfg: 应用配置对象
        llm: LLM客户端实例
        localizer: 文件本地化实例
        
    Notes:
        - 所有分析都使用LLM进行内容理解
        - 自动识别内容语言
        - 返回JSON格式：{"language": "...", "analysis": "..."}
    """
    
    def __init__(self, cfg: AppConfig, llm: LLMClient, localizer: Localizer):
        self.cfg = cfg
        self.llm = llm
        self.localizer = localizer

    async def analyze(self, url: str, file_type: Optional[str] = None) -> Dict[str, str]:
        """
        分析指定URL的内容
        
        Args:
            url: 文件URL或本地路径
            file_type: 文件类型（可选），如果不指定则自动推断
                支持的类型：image, video, pdf, docx, web_url, txt
                
        Returns:
            分析结果字典，包含：
            - language: 识别的语言代码（如 "en", "zh", "unknown"）
            - analysis: 内容分析/描述
            
        Notes:
            - 根据文件类型调用相应的分析方法
            - 自动推断文件类型（基于URL后缀）
            - 所有方法都使用LLM进行内容理解
        """
        ftype = file_type or _infer_type_from_url(url)
        logger.info(f"[Analyzer] start | type={ftype} | url={url}")

        if ftype == "image":
            return await self._analyze_image(url)
        if ftype == "video":
            return await self._analyze_video(url)
        if ftype == "pdf":
            return await self._analyze_pdf(url)
        if ftype == "docx":
            return await self._analyze_docx(url)
        if ftype == "web_url":
            return await self._analyze_web(url)

        return await self._analyze_text(url)

    async def _analyze_image(self, url: str) -> Dict[str, str]:
        """
        分析图片内容
        
        Args:
            url: 图片URL或本地路径
            
        Returns:
            分析结果字典，包含language和analysis
            
        Notes:
            - 使用PIL库检测图片格式
            - 将图片转换为Base64编码发送给LLM
            - 支持的格式：JPG, PNG, WebP, GIF, BMP
            - 失败时返回错误信息
        """
        try:
            from PIL import Image
        except Exception as e:
            return {"language": "unknown", "analysis": f"PIL not available: {type(e).__name__}: {e}"}

        suffix = Path(urlparse(url).path).suffix or ".jpg"
        local_path, cleanup = await self.localizer.ensure_local_async(url, suffix)

        try:
            mime = "image/jpeg"
            def _detect_mime() -> str:
                # 检测图片的MIME类型
                with Image.open(local_path) as im:
                    fmt = (im.format or "").lower()
                    if fmt == "png":
                        return "image/png"
                    if fmt == "webp":
                        return "image/webp"
                    if fmt in ("jpg", "jpeg"):
                        return "image/jpeg"
                    return mimetypes.guess_type(local_path)[0] or "image/jpeg"

            mime = await asyncio.to_thread(_detect_mime)

            content = [
                {"type": "text", "text": _build_analyze_prompt()},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{_b64_of_file(local_path)}"}},
            ]
            raw = await self.llm.chat(self.cfg.analyze_model, content, temperature=0.2)
            obj = _parse_json_strict(raw) or {}
            return {"language": str(obj.get("language", "unknown")), "analysis": str(obj.get("analysis", raw)).strip()}
        finally:
            # 清理临时文件
            if cleanup and os.path.exists(local_path):
                os.unlink(local_path)

    async def _analyze_video(self, url: str) -> Dict[str, str]:
        """
        分析视频内容
        
        Args:
            url: 视频URL或本地路径
            
        Returns:
            分析结果字典，包含language和analysis
            
        Notes:
            - 使用OpenCV提取关键帧
            - 在配置的时间点采样帧（默认：0%, 50%, 90%）
            - 将帧转换为JPG图片发送给LLM
            - 支持的格式：MP4, MOV, AVI, MKV, FLV
            - 失败时返回错误信息
        """
        try:
            import cv2
        except Exception as e:
            return {"language": "unknown", "analysis": f"cv2 not available: {type(e).__name__}: {e}"}

        suffix = Path(urlparse(url).path).suffix or ".mp4"
        local_path, cleanup = await self.localizer.ensure_local_async(url, suffix)

        cap = None
        try:
            # cv2是阻塞操作，在线程中执行
            def _extract_frames() -> Tuple[float, int, float, List[Dict[str, str]]]:
                nonlocal cap
                cap = cv2.VideoCapture(local_path)
                if not cap.isOpened():
                    return 0.0, 0, 0.0, []

                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                duration = (total / fps) if (fps > 0 and total > 0) else 0.0

                # 在指定时间点提取帧
                images: List[Dict[str, str]] = []
                for tp in self.cfg.video_time_points:
                    if duration > 0:
                        # 根据时间百分比设置帧位置
                        cap.set(cv2.CAP_PROP_POS_MSEC, tp * duration * 1000.0)
                    else:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

                    ok, frame = cap.read()
                    if not ok or frame is None:
                        continue
                    ok2, buf = cv2.imencode(".jpg", frame)
                    if not ok2:
                        continue
                    # 将帧编码为Base64
                    images.append({"mime": "image/jpeg", "b64": base64.b64encode(buf).decode("utf-8")})
                return fps, total, duration, images

            fps, total, duration, images = await asyncio.to_thread(_extract_frames)
            logger.info(f"[Analyzer][Video] meta | fps={fps:.2f} | frames={total} | duration={duration:.2f}s")

            if not images:
                return {"language": "unknown", "analysis": "No frames extracted from video."}

            # 将所有帧发送给LLM分析
            content = [{"type": "text", "text": _build_analyze_prompt()}]
            for it in images:
                content.append({"type": "image_url", "image_url": {"url": f"data:{it['mime']};base64,{it['b64']}"}})

            raw = await self.llm.chat(self.cfg.analyze_model, content, temperature=0.2)
            obj = _parse_json_strict(raw) or {}
            return {"language": str(obj.get("language", "unknown")), "analysis": str(obj.get("analysis", raw)).strip()}
        finally:
            # 释放视频捕获对象
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
            # 清理临时文件
            if cleanup and os.path.exists(local_path):
                os.unlink(local_path)

    async def _analyze_pdf(self, url: str) -> Dict[str, str]:
        """
        分析PDF文档内容
        
        Args:
            url: PDF文件URL或本地路径
            
        Returns:
            分析结果字典，包含language和analysis
            
        Notes:
            - 优先使用视觉模式（OCR）：将页面渲染为图片
            - 视觉模式失败时回退到文本提取
            - 文本提取使用PyPDF2库
            - 仅提取第一页的文本预览（最多1200字符）
        """
        local_path, cleanup = await self.localizer.ensure_local_async(url, ".pdf")
        try:
            # 可选：使用视觉模式（OCR）
            if self.cfg.enable_pdf_vision:
                try:
                    import fitz  # pymupdf

                    def _render_pages() -> List[bytes]:
                        # 渲染PDF页面为图片
                        doc = fitz.open(local_path)
                        n = min(self.cfg.pdf_vision_pages, doc.page_count)
                        out = []
                        for i in range(n):
                            page = doc.load_page(i)
                            # 使用160 DPI渲染页面
                            pix = page.get_pixmap(dpi=160)
                            out.append(pix.tobytes("png"))
                        return out

                    png_pages = await asyncio.to_thread(_render_pages)
                    content = [{"type": "text", "text": _build_analyze_prompt()}]
                    for png_bytes in png_pages:
                        content.append(
                            {"type": "image_url",
                             "image_url": {"url": f"data:image/png;base64,{_b64_of_bytes(png_bytes)}"}}
                        )
                    raw = await self.llm.chat(self.cfg.analyze_model, content, temperature=0.2)
                    obj = _parse_json_strict(raw) or {}
                    return {"language": str(obj.get("language", "unknown")), "analysis": str(obj.get("analysis", raw)).strip()}
                except Exception as e:
                    logger.info(f"[Analyzer][PDF] vision failed -> fallback text | err={type(e).__name__}: {e}")

            # 文本提取回退方案
            try:
                import PyPDF2
            except Exception as e:
                return {"language": "unknown", "analysis": f"PyPDF2 not available: {type(e).__name__}: {e}"}

            def _extract_preview() -> str:
                # 提取PDF文本预览
                with open(local_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    if not reader.pages:
                        return ""
                    return (reader.pages[0].extract_text() or "")[:1200]

            preview = await asyncio.to_thread(_extract_preview)
            prompt = _build_analyze_prompt() + "\nExtracted text preview:\n" + preview
            content = [{"type": "text", "text": prompt}]

            raw = await self.llm.chat(self.cfg.analyze_model, content, temperature=0.2)
            obj = _parse_json_strict(raw) or {}
            return {"language": str(obj.get("language", "unknown")), "analysis": str(obj.get("analysis", raw)).strip()}
        finally:
            # 清理临时文件
            if cleanup and os.path.exists(local_path):
                os.unlink(local_path)

    async def _analyze_docx(self, url: str) -> Dict[str, str]:
        """
        分析Word文档内容
        
        Args:
            url: DOCX文件URL或本地路径
            
        Returns:
            分析结果字典，包含language和analysis
            
        Notes:
            - 使用python-docx库提取文本
            - 提取所有段落的文本
            - 使用_safe_preview处理文本（最多1200字符）
        """
        local_path, cleanup = await self.localizer.ensure_local_async(url, ".docx")
        try:
            try:
                from docx import Document
            except Exception as e:
                return {"language": "unknown", "analysis": f"python-docx not available: {type(e).__name__}: {e}"}

            def _read_docx() -> str:
                # 读取Word文档文本
                doc = Document(local_path)
                text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                return _safe_preview(text, 1200)

            preview = await asyncio.to_thread(_read_docx)
            prompt = _build_analyze_prompt() + "\nExtracted text preview:\n" + preview
            content = [{"type": "text", "text": prompt}]

            raw = await self.llm.chat(self.cfg.analyze_model, content, temperature=0.2)
            obj = _parse_json_strict(raw) or {}
            return {"language": str(obj.get("language", "unknown")), "analysis": str(obj.get("analysis", raw)).strip()}
        finally:
            # 清理临时文件
            if cleanup and os.path.exists(local_path):
                os.unlink(local_path)

    async def _analyze_text(self, url: str) -> Dict[str, str]:
        """
        分析纯文本文件内容
        
        Args:
            url: 文本文件URL或本地路径
            
        Returns:
            分析结果字典，包含language和analysis
            
        Notes:
            - 直接读取文件内容
            - 使用UTF-8编码，忽略错误字符
            - 使用_safe_preview处理文本（最多1200字符）
        """
        suffix = Path(urlparse(url).path).suffix or ".txt"
        local_path, cleanup = await self.localizer.ensure_local_async(url, suffix)
        try:
            def _read_text() -> str:
                # 读取文本文件
                return Path(local_path).read_text(encoding="utf-8", errors="ignore")

            text = await asyncio.to_thread(_read_text)
            preview = _safe_preview(text, 1200)

            prompt = _build_analyze_prompt() + "\nText preview:\n" + preview
            content = [{"type": "text", "text": prompt}]

            raw = await self.llm.chat(self.cfg.analyze_model, content, temperature=0.2)
            obj = _parse_json_strict(raw) or {}
            return {"language": str(obj.get("language", "unknown")), "analysis": str(obj.get("analysis", raw)).strip()}
        finally:
            # 清理临时文件
            if cleanup and os.path.exists(local_path):
                os.unlink(local_path)

    async def _analyze_web(self, url: str) -> Dict[str, str]:
        """
        分析网页内容
        
        Args:
            url: 网页URL
            
        Returns:
            分析结果字典，包含language和analysis
            
        Notes:
            - 使用requests获取网页HTML
            - 使用BeautifulSoup解析HTML
            - 移除script、style、noscript等标签
            - 提取标题和正文文本
            - 使用_safe_preview处理文本（最多1200字符）
        """
        def _fetch_html() -> str:
            # 获取网页HTML
            r = requests.get(url, timeout=self.cfg.http_timeout)
            r.raise_for_status()
            return r.text

        html = await asyncio.to_thread(_fetch_html)

        # 解析HTML并移除脚本和样式标签
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()

        # 提取标题和正文
        title = (soup.title.string or "").strip() if soup.title and soup.title.string else "Untitled"
        text = soup.get_text(separator="\n", strip=True)
        preview = _safe_preview(text, 1200)

        prompt = _build_analyze_prompt() + f"\nTitle: {title}\nWeb text preview:\n{preview}"
        content = [{"type": "text", "text": prompt}]

        raw = await self.llm.chat(self.cfg.analyze_model, content, temperature=0.2)
        obj = _parse_json_strict(raw) or {}
        return {"language": str(obj.get("language", "unknown")), "analysis": str(obj.get("analysis", raw)).strip()}


# ============================================================
# Agnes comment (difference-aware)
# ============================================================

def build_agnes_diff_prompt(context: str, diff_summary: str, target_lang: str) -> str:
    """
    构建Agnes评论生成的Prompt
    
    Args:
        context: 聊天上下文，用于理解用户关注点
        diff_summary: 用户上传与生成结果的对比摘要
        target_lang: 目标语言代码（如 "zh", "en"）
        
    Returns:
        评论生成任务的Prompt字符串
        
    Notes:
        - 要求LLM以Agnes身份生成友好、自然的评论
        - 评论需要包含创意亮点和技术执行两个方面
        - 结尾提供帮助写分享文案的CTA
        - 根据语言设置不同的长度限制
        - 中文：50-80字符
        - 英文：30-60单词
    """
    lang_name = _language_name_for_prompt(target_lang)

    length_rule = (
        "Comments length: 50-80 Chinese characters"
        if _is_zh(target_lang)
        else "Comments length: 30-60 words"
    )

    return f"""You are Agnes, an AI assistant. Write a friendly, complimentary comment about the GENERATED RESULT,
based on the comparison between USER UPLOADS and the GENERATED RESULT.

Requirements:
1. Sound like a real friend (casual, warm), not formal writing
2. Use natural conversational language
3. Use the chat context ONLY as background to infer what the user cares about (tone, intent, topic)
4. Make the comment closely related to the diff summary below (avoid generic praise)
5. Do NOT quote or repeat the chat context verbatim; do NOT mention private details; do NOT summarize the conversation
6. {length_rule}
7. The comment MUST cover these angles (keep it short, no long lectures):
   - Creative highlight (positive first): point out 1 standout creative idea or “wow” moment.
   - Technical execution: mention 1 aspect such as editing rhythm / pacing / visuals / lighting / transitions / music sync.
8. End with a polite, slightly “Microsoft assistant” style question offering to help write 2-4 shareable captions.
   - The CTA must connect to your compliment (what looks good / what stands out).
   - Vary wording each time; avoid sounding like a system notification or marketing.
9. Return ONLY ONE short message (no bullet points, no extra text). Up to 2-3 short sentences is OK.
10. The structure and wording should vary each time
11. Write the comment in {lang_name} ONLY

Chat context (for reference only, do not repeat):
{context}

Diff summary (user uploads vs generated result):
{diff_summary}

Generate the message now:
"""


def enforce_length_or_raise(greeting: str, target_lang: str) -> str:
    """
    强制检查评论长度，不符合则抛出异常
    
    Args:
        greeting: 待检查的评论文本
        target_lang: 目标语言代码
        
    Returns:
        清理后的评论文本
        
    Raises:
        ValueError: 评论长度不符合要求
            - 中文：长度不在50-80字符之间
            - 英文：单词数不在30-60之间
            
    Notes:
        - 使用_clean_quotes_punct清理文本
        - 中文按字符数统计
        - 英文按单词数统计
    """
    g = _clean_quotes_punct(greeting)

    if _is_zh(target_lang):
        if len(g) < 50 or len(g) > 80:
            raise ValueError(f"中文长度不合规: {len(g)} chars")
        return g

    wc = _word_count_en(g)
    if wc < 30 or wc > 60:
        raise ValueError(f"词数不合规: {wc} words")
    return g


def fallback_comment(target_lang: str) -> str:
    """
    获取备用评论（当LLM生成失败时使用）
    
    Args:
        target_lang: 目标语言代码
        
    Returns:
        备用评论文本
        
    Notes:
        - 中文："整体提升挺明显的！你满意现在的效果吗？"
        - 英文："This looks awesome—are you happy with it, or want any tweaks?"
        - 其他语言使用英文版本
    """
    if _is_zh(target_lang):
        return "整体提升挺明显的！你满意现在的效果吗？"
    return "This looks awesome—are you happy with it, or want any tweaks?"


def choose_target_language(parsed_lang: str, language_code: str) -> str:
    """
    选择目标语言
    
    Args:
        parsed_lang: 从内容分析中解析出的语言代码
        language_code: 用户指定的语言代码
        
    Returns:
        最终选择的语言代码
        
    Notes:
        - 优先使用解析出的语言（如果不是unknown）
        - 其次使用用户指定的语言代码
        - 默认返回"en"
    """
    if parsed_lang and parsed_lang != "unknown":
        return parsed_lang
    if language_code:
        return language_code
    return "en"


def _format_diff_for_comment(diff_obj: Dict[str, Any]) -> str:
    """
    格式化对比结果为评论Prompt使用的字符串
    
    Args:
        diff_obj: 对比结果对象，包含：
            - summary: 总体对比摘要
            - differences: 关键差异列表
            - suggestions: 建议
            
    Returns:
        格式化后的对比字符串
        
    Notes:
        - 提取summary、differences（最多3个）、suggestions
        - 使用换行符连接各部分
        - 用于构建评论Prompt
    """
    summary = str(diff_obj.get("summary", "")).strip()
    diffs = diff_obj.get("differences") or []
    diffs = [str(x).strip() for x in diffs if str(x).strip()]
    diffs_txt = "; ".join(diffs[:3])
    sugg = str(diff_obj.get("suggestions", "")).strip()

    chunks = []
    if summary:
        chunks.append(summary)
    if diffs_txt:
        chunks.append(f"Key differences: {diffs_txt}")
    if sugg:
        chunks.append(f"Suggestion: {sugg}")
    return "\n".join(chunks).strip()


# ============================================================
# Pipeline V2
# ============================================================

class PipelineV2:
    """
    Agnes流水线V2 - 完整的内容分析和评论生成流程
    
    主要功能：
    1. 并行分析用户上传的多个文件（有界并发控制）
    2. 分析生成的结果文件
    3. 汇总用户上传材料的分析结果
    4. 对比用户上传和生成结果的差异
    5. 基于差异和上下文生成Agnes评论
    
    特性：
    - 异步处理，避免阻塞
    - 有界并发控制（防止资源耗尽）
    - 自动降级策略（LLM失败时使用备用评论）
    - 支持多种文件类型（图片、视频、PDF、DOCX、网页、文本）
    
    Attributes:
        cfg: 应用配置对象
        llm: LLM客户端实例
        localizer: 文件本地化实例
        analyzer: 内容分析器实例
        _sem: 并发控制信号量
        
    Notes:
        - 用户上传和生成结果分析并行执行
        - 所有阻塞I/O操作都移到线程池
        - 使用asyncio.gather并行处理多个文件
    """
    
    def __init__(self, cfg: Optional[AppConfig] = None):
        self.cfg = cfg or AppConfig()
        self.llm = LLMClient(self.cfg)
        self.localizer = Localizer(self.cfg)
        self.analyzer = ContentAnalyzer(self.cfg, self.llm, self.localizer)

        # 有界并发控制：下载/解码/PDF渲染/LLM调用
        c = max(1, int(self.cfg.analyze_concurrency or 1))
        self._sem = asyncio.Semaphore(c)

    async def _analyze_one(self, idx: int, url: str, file_type: Optional[str] = None) -> Dict[str, str]:
        """
        分析单个文件（受并发控制）
        
        Args:
            idx: 文件索引（用于日志）
            url: 文件URL或本地路径
            file_type: 文件类型（可选）
                
        Returns:
            分析结果字典，包含：
            - url: 文件URL
            - language: 识别的语言代码
            - analysis: 内容分析/描述（失败时包含错误信息）
            
        Notes:
            - 使用信号量控制并发数量
            - 失败时返回包含错误信息的字典
            - 记录详细的日志（成功/失败、耗时、语言等）
        """
        async with self._sem:
            t0 = time.time()
            try:
                r = await self.analyzer.analyze(url, file_type=file_type)
                dt = (time.time() - t0) * 1000
                logger.info(
                    f"[UserAnalyze] ok | i={idx} | ms={dt:.0f} | lang={r.get('language')} | type={file_type or 'auto'} | url={url}"
                )
                return {"url": url, "language": r.get("language", "unknown"), "analysis": r.get("analysis", "")}
            except Exception as e:
                dt = (time.time() - t0) * 1000
                logger.warning(
                    f"[UserAnalyze] fail | i={idx} | ms={dt:.0f} | type={file_type or 'auto'} | url={url} | err={type(e).__name__}: {e}"
                )
                return {"url": url, "language": "unknown", "analysis": f"(analysis failed: {type(e).__name__}: {e})"}

    async def _analyze_many(self, urls: List[str], file_types: Optional[List[Optional[str]]] = None) -> List[Dict[str, str]]:
        """
        并行分析多个文件
        
        Args:
            urls: 文件URL或本地路径列表
            file_types: 对应的文件类型列表（可选）
                
        Returns:
            分析结果字典列表，每个包含url、language、analysis
            
        Notes:
            - 受max_user_items配置限制
            - 使用asyncio.gather并行执行
            - 每个文件都受并发信号量控制
            - 记录批量处理的统计信息
        """
        urls = urls or []
        limit = max(1, int(self.cfg.max_user_items or 1))

        if len(urls) > limit:
            logger.info(f"[UserBatch] truncate | n_in={len(urls)} -> n_use={limit} | limit={limit}")

        use_urls = urls[:limit]

        if file_types:
            use_types = (file_types + [None] * limit)[:len(use_urls)]
        else:
            use_types = [None] * len(use_urls)

        # 创建并行任务
        tasks = [
            asyncio.create_task(self._analyze_one(idx=i, url=u, file_type=use_types[i]))
            for i, u in enumerate(use_urls)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        logger.info(f"[UserBatch] done | n={len(results)} | concurrency={self.cfg.analyze_concurrency}")
        return results

    async def _bundle_user_reference(self, user_items: List[Dict[str, str]]) -> Dict[str, str]:
        """
        汇总用户上传材料的分析结果
        
        Args:
            user_items: 用户文件分析结果列表，每个包含url、language、analysis
                
        Returns:
            汇总结果字典，包含：
            - language: 主要语言代码
            - reference: 统一的参考摘要
            
        Notes:
            - 将多个分析结果合并为一个简洁的参考
            - 使用LLM进行智能汇总
            - 记录汇总耗时和预览
        """
        joined = "\n\n".join(
            [f"- URL: {x['url']}\n  analysis: {x['analysis']}" for x in user_items if x.get("analysis")]
        )
        prompt = _build_user_bundle_prompt() + "\n\nUser materials analyses:\n" + joined
        content = [{"type": "text", "text": prompt}]

        t0 = time.time()
        raw = await self.llm.chat(self.cfg.analyze_model, content, temperature=0.2)
        dt = (time.time() - t0) * 1000
        obj = _parse_json_strict(raw) or {}
        lang = str(obj.get("language", "unknown"))
        ref = str(obj.get("reference", raw)).strip()
        logger.info(f"[UserBundle] done | ms={dt:.0f} | lang={lang} | ref_preview={ref[:160]!r}")
        return {"language": lang, "reference": ref}

    async def _diff_compare(self, user_ref: str, gen_ref: str) -> Dict[str, Any]:
        """
        对比用户上传和生成结果的差异
        
        Args:
            user_ref: 用户上传材料的参考描述
            gen_ref: 生成结果的参考描述
                
        Returns:
            对比结果字典，包含：
            - language: 识别的语言代码
            - summary: 总体对比摘要
            - differences: 关键差异列表
            - improvements: 生成结果的改进点
            - issues: 问题或缺失点
            - suggestions: 建议
            
        Notes:
            - 使用LLM进行智能对比
            - 记录对比耗时和预览
            - 返回的JSON可能不完整，使用默认值
        """
        prompt = _build_diff_prompt(user_ref=user_ref, gen_ref=gen_ref)
        content = [{"type": "text", "text": prompt}]
        t0 = time.time()
        raw = await self.llm.chat(self.cfg.analyze_model, content, temperature=0.2)
        dt = (time.time() - t0) * 1000
        obj = _parse_json_strict(raw) or {"language": "unknown", "summary": raw}
        logger.info(f"[Diff] done | ms={dt:.0f} | preview={str(obj.get('summary',''))[:160]!r}")
        return obj

    async def run(
        self,
        user_upload_url: List[str],
        s3_url: str,
        language_code: str,
        context: str,
        user_file_types: Optional[List[Optional[str]]] = None,
        s3_file_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行完整的Agnes流水线
        
        Args:
            user_upload_url: 用户上传的文件URL列表
            s3_url: 生成结果的S3 URL（必填）
            language_code: 目标语言代码
            context: 聊天上下文，用于理解用户关注点
            user_file_types: 用户上传文件的类型列表（可选）
            s3_file_type: 生成结果的文件类型（可选）
                
        Returns:
            流水线执行结果字典，包含：
            - success: 是否成功（True，即使使用降级方案）
            - greeting: 生成的评论文本
            - analysis_language_user: 用户材料分析的语言
            - analysis_language_gen: 生成结果分析的语言
            - analysis_language_diff: 对比分析的语言
            - target_language: 最终使用的目标语言
            - fallback: 是否使用了降级方案
            - user_reference: 用户材料汇总参考
            - gen_analysis: 生成结果分析
            - diff: 对比结果对象
            - user_items_used: 实际使用的用户文件数
            - user_items_total: 用户上传的文件总数
            
        Raises:
            ValueError: s3_url为空
            
        Notes:
            执行流程：
            1. 并行分析用户上传和生成结果
            2. 汇总用户上传材料的分析
            3. 对比用户上传和生成结果
            4. 选择目标语言
            5. 生成Agnes评论（支持重试）
            6. 失败时使用备用评论
            
            - 用户上传和生成结果分析并行执行
            - 评论生成支持多次重试（comment_retries配置）
            - 所有步骤都有详细的日志记录
        """
        t_start = time.time()
        user_upload_url = user_upload_url or []

        logger.info(
            f"[PipelineV2] start | user_n={len(user_upload_url)} | max_user_items={self.cfg.max_user_items} | "
            f"s3_url={s3_url} | lang_code={language_code}"
        )

        if not s3_url:
            raise ValueError("s3_url is required")

        # 并行：用户批量分析 + 生成结果分析
        user_task = asyncio.create_task(self._analyze_many(user_upload_url, file_types=user_file_types)) if user_upload_url else None
        gen_task = asyncio.create_task(self.analyzer.analyze(s3_url, file_type=s3_file_type))

        user_items = await user_task if user_task else []
        gen_res = await gen_task

        logger.info(f"[PipelineV2] user analyzed | n={len(user_items)}")
        gen_lang = gen_res.get("language", "unknown")
        gen_ref = gen_res.get("analysis", "")
        logger.info(f"[PipelineV2] gen analyzed | lang={gen_lang} | preview={gen_ref[:160]!r}")

        # 汇总用户上传材料
        if user_items:
            user_bundle = await self._bundle_user_reference(user_items)
            user_ref_lang = user_bundle.get("language", "unknown")
            user_ref = user_bundle.get("reference", "")
        else:
            user_ref_lang = "unknown"
            user_ref = "(no user uploads provided)"

        # 对比分析
        diff_obj = await self._diff_compare(user_ref=user_ref, gen_ref=gen_ref)
        diff_lang = str(diff_obj.get("language", "unknown"))

        # 选择评论语言
        # target_lang = choose_target_language(
        #     parsed_lang=(diff_lang if diff_lang and diff_lang != "unknown" else gen_lang),
        #     language_code=language_code)
        target_lang = language_code  # 使用上下文获取语种
        logger.info(f"[PipelineV2] target_lang={target_lang} | user_ref_lang={user_ref_lang} | gen_lang={gen_lang} | diff_lang={diff_lang}")

        # 生成Agnes评论（支持重试）
        diff_for_comment = _format_diff_for_comment(diff_obj)
        prompt = build_agnes_diff_prompt(context=context, diff_summary=diff_for_comment, target_lang=target_lang)
        content = [{"type": "text", "text": prompt}]

        last_err: Optional[Exception] = None
        for attempt in range(max(1, int(self.cfg.comment_retries or 1))):
            try:
                raw = await self.llm.chat(self.cfg.comment_model, content, temperature=1.2)
                # greeting = enforce_length_or_raise(raw, target_lang)  # 暂不限制长度
                greeting = raw
                total_ms = (time.time() - t_start) * 1000
                logger.info(f"[PipelineV2] done | ms={total_ms:.0f} | fallback=False | attempt={attempt+1} | greeting={greeting!r}")

                return {
                    "success": True,
                    "greeting": greeting,
                    "analysis_language_user": user_ref_lang,
                    "analysis_language_gen": gen_lang,
                    "analysis_language_diff": diff_lang,
                    "target_language": target_lang,
                    "fallback": False,

                    # 调试/存储
                    "user_reference": user_ref,
                    "gen_analysis": gen_ref,
                    "diff": diff_obj,

                    "user_items_used": len(user_items),
                    "user_items_total": len(user_upload_url),
                }
            except Exception as e:
                last_err = e
                logger.warning(f"[PipelineV2] comment attempt failed | attempt={attempt+1} | err={type(e).__name__}: {e}")

        # 所有尝试失败，使用备用评论
        total_ms = (time.time() - t_start) * 1000
        logger.warning(f"[PipelineV2] comment failed -> fallback | ms={total_ms:.0f} | err={type(last_err).__name__ if last_err else 'Unknown'}: {last_err}")
        greeting = fallback_comment(target_lang)

        return {
            "success": True,
            "greeting": greeting,
            "analysis_language_user": user_ref_lang,
            "analysis_language_gen": gen_lang,
            "analysis_language_diff": diff_lang,
            "target_language": target_lang,
            "fallback": True,

            "user_reference": user_ref,
            "gen_analysis": gen_ref,
            "diff": diff_obj,

            "user_items_used": len(user_items),
            "user_items_total": len(user_upload_url),
        }


# ==========================
# Demo
# ==========================

if __name__ == "__main__":
    """
    Before run:
      - export LLM_API_KEY=xxxx
      - optional: LLM_BASE_URL / LLM_ANALYZE_MODEL / LLM_CHAT_CHECK_MODEL
    """

    async def main():
        user_upload_url = [
            "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/d40be33f-ff52-4eaa-a6b5-87ee8f5b8520.webp",
            "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/1aee2e98-e5d4-4193-84b8-e65b6f6a1c71.jpeg",
            # can provide more; will truncate to MAX_USER_ITEMS
        ]
        s3_url = "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03-watermarks/water-njTuFMpL.png"

        language_code = "zh"
        context = "用户希望把上传素材生成更清晰、更有质感的成品。"

        pipe = PipelineV2()
        start_time = time.time()
        out = await pipe.run(
            user_upload_url=user_upload_url,
            s3_url=s3_url,
            language_code=language_code,
            context=context,
        )
        elapsed = time.time() - start_time

        print(f"Pipeline 执行耗时: {elapsed:.2f} 秒")
        print("Greeting:", out["greeting"])
        # print(out)

    asyncio.run(main())
