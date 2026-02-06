
import pytest
import httpx
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.routers.event.commentary_url import call_gemini_compare_and_comment

test_case = {
    "case1": {
        "input_urls": ["https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03-watermarks/water-YtnuyJhQ.png",
                "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03-watermarks/water-ScqeFrcV.png"],
        "output_url": "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03_videos-watermarks/water-cgt-20260112144758-bsf5z.mp4"
    },
    "case2": {
        "input_urls": ["https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03-watermarks/water-HCCES6kP.png",
                "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03-watermarks/water-JVbNyhmr.png"],
        "output_url": "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03_videos-watermarks/water-cgt-20260112104747-b7lgx.mp4"
    },
    "case3": {
        "input_urls": ["https://agnes-dev.kiwiar.com/gcs-agnes-aigc/d40be33f-ff52-4eaa-a6b5-87ee8f5b8520.webp",
                "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/1aee2e98-e5d4-4193-84b8-e65b6f6a1c71.jpeg"],
        "output_url": "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03-watermarks/water-njTuFMpL.png"
    }
}

class TestCallGeminiCompareAndComment:
    """测试 call_gemini_compare_and_comment 函数"""
    @pytest.mark.asyncio
    async def test_success_video(self):
        """测试成功生成视频点评的场景"""
        for case_name, case_data in test_case.items():
            # if case_name == "case1":
            #     continue
            image_urls = case_data["input_urls"]
            generated_url = case_data["output_url"]
            generated_type = "video"

            result = await call_gemini_compare_and_comment(
                image_urls=image_urls,
                generated_url=generated_url,
                generated_type=generated_type,
                language_code="zh"
            )
            print(f"case {case_name}, result {result['comment']}")
            assert result["comment"]

    @pytest.mark.asyncio
    async def test_concurrent_success_video(self):
        """并发测试成功生成视频点评的场景"""
        tasks = []
        for case_name, case_data in test_case.items():
            image_urls = case_data["input_urls"]
            generated_url = case_data["output_url"]
            generated_type = "video"

            tasks.append(call_gemini_compare_and_comment(
                image_urls=image_urls,
                generated_url=generated_url,
                generated_type=generated_type,
                language_code="zh"
            ))

        results = await asyncio.gather(*tasks)
        
        for idx, result in enumerate(results):
            case_name = list(test_case.keys())[idx]
            print(f"case {case_name}, result {result['comment']}")
            assert result["comment"]

    @pytest.mark.asyncio
    async def test_concurrent_10_times(self):
        """测试 10 次并发调用的场景，循环使用 3 个 case"""
        tasks = []
        case_keys = list(test_case.keys())
        for i in range(10):
            case_name = case_keys[i % len(case_keys)]
            case_data = test_case[case_name]
            image_urls = case_data["input_urls"]
            generated_url = case_data["output_url"]
            generated_type = "video" if generated_url.endswith(".mp4") else "image"
            
            # 不等待，直接创建协程任务放入列表
            tasks.append(call_gemini_compare_and_comment(
                image_urls=image_urls,
                generated_url=generated_url,
                generated_type=generated_type,
                language_code="zh"
            ))
        
        # 并发执行并等待结果
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        for i, result in enumerate(results):
            print(f"Call {i+1}, result: {result['comment']}")
            assert result["comment"]

