import asyncio
import time
import random
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from app.routers.event.commentary_url import call_gemini_compare_and_comment

test_case = {
    "case1": {
        "user_upload_url": ["https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03-watermarks/water-YtnuyJhQ.png",
                            "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03-watermarks/water-ScqeFrcV.png"],
        "s3_url": "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03_videos-watermarks/water-cgt-20260112144758-bsf5z.mp4"
    },
    "case2": {
        "user_upload_url": ["https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03-watermarks/water-HCCES6kP.png",
                            "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03-watermarks/water-JVbNyhmr.png"],
        "s3_url": "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03_videos-watermarks/water-cgt-20260112104747-b7lgx.mp4"
    },
    "case3": {
        "user_upload_url": ["https://agnes-dev.kiwiar.com/gcs-agnes-aigc/d40be33f-ff52-4eaa-a6b5-87ee8f5b8520.webp",
                            "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/1aee2e98-e5d4-4193-84b8-e65b6f6a1c71.jpeg"],
        "s3_url": "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03-watermarks/water-njTuFMpL.png"
    },
    "case4": {
        "user_upload_url": ["https://agnes-dev.kiwiar.com/gcs-agnes-aigc/28b49738-137f-4bb8-abb0-15e8c0d9946a.jpeg"],
        "s3_url": "https://agnes-dev.kiwiar.com/gcs-agnes-default/merge_audio_videos/33fc5796-c5c4-4ae3-824a-8e1ad9cef07e.mp4"
    },
    "case5": {
        "user_upload_url": ["https://agnes-dev.kiwiar.com/gcs-agnes-aigc/d388efdf-a4d8-41f3-8600-d60ee706568e.jpeg",
                            "https://cdn-s3-agnes-test-sg.agnes-ai.com/fe0b3a6a-fae8-4ad7-a40a-5649cab4a553.jpg"],
        "s3_url": "https://agnes-dev.kiwiar.com/gcs-agnes-aigc/m03_videos-watermarks/water-cgt-20260113114533-mzzq6.mp4"
    },
    "case6": {
        "user_upload_url": ["https://agnes-dev.kiwiar.com/gcs-agnes-aigc/d388efdf-a4d8-41f3-8600-d60ee706568e.jpeg",
                            "https://cdn-s3-agnes-test-sg.agnes-ai.com/fe0b3a6a-fae8-4ad7-a40a-5649cab4a553.jpg"],
        "s3_url": "https://agnes-test-gcp.kiwiar.com/gcs-agnes-default/merge_audio_videos/f83e38cb-bf6f-4796-a1fe-e1dfb6646831.mp4"
    }
}

good_case = [
    {
        "input_urls": ['https://agnes-test-gcp.kiwiar.com/gcs-agnes-aigc/9cbea75c-b7a9-4347-b21d-4b6a87d4a10b.png'], 
        "output_url": "https://agnes-test-gcp.kiwiar.com/gcs-agnes-aigc/m03-watermarks/water-SeRBVNA6.png"
    },
    {
        "input_urls": ['https://agnes-test-gcp.kiwiar.com/gcs-agnes-aigc/929df5c5-690e-4d27-bcbb-801554bf7b7e.png'], 
        "output_url": "https://agnes-test-gcp.kiwiar.com/gcs-agnes-aigc/m03-watermarks/water-PJCZFSmM.png"
    },
    {
        "input_urls": ['https://agnes-test-gcp.kiwiar.com/gcs-agnes-aigc/91c91ac4-9c83-4fec-a477-8aea60968339.png'], 
        "output_url": "https://agnes-test-gcp.kiwiar.com/gcs-agnes-aigc/m03_videos-watermarks/water-cgt-20260122114352-68vwt.mp4"
    },
    {
        "input_urls": ['https://agnes-test-gcp.kiwiar.com/gcs-agnes-aigc/b4dfffbe-1b23-40ce-9777-03bf2bb20b7f.png'], 
        "output_url": "https://agnes-test-gcp.kiwiar.com/gcs-agnes-default/merge_audio_videos/9346a823-4d8d-4a0a-80a0-375be9ab4c49.mp4"
    },
    {
        "input_urls": ['https://agnes-test-gcp.kiwiar.com/gcs-agnes-aigc/42de51cf-ffd4-4236-8b01-1842b836ebbb.png'], 
        "output_url": "https://agnes-test-gcp.kiwiar.com/gcs-agnes-aigc/m03_videos-watermarks/water-cgt-20260122114145-c68c4.mp4"
    },
    {
        "input_urls": ['https://agnes-test-gcp.kiwiar.com/gcs-agnes-aigc/f0cbfd2e-c801-4764-be62-8b94c2e81a60.png'], 
        "output_url": "https://agnes-test-gcp.kiwiar.com/gcs-agnes-default/merge_audio_videos/6ff3a07b-352f-44a6-8aa7-6dd5a12950a3.mp4"
    },
    {
        "input_urls": ['https://agnes-test-gcp.kiwiar.com/gcs-agnes-aigc/25dcad89-bde7-4c15-8c8f-2a8afb55dbec.png'], 
        "output_url": "https://agnes-test-gcp.kiwiar.com/gcs-agnes-default/merge_audio_videos/78c35ea5-0a04-4b90-83c9-a88af7f705eb.mp4"
    },
    {
        "input_urls": ['https://agnes-test-gcp.kiwiar.com/gcs-agnes-aigc/9a4cf9ae-97c1-4d32-8e26-fddf2d2a35d1.png'], 
        "output_url": "https://agnes-test-gcp.kiwiar.com/gcs-agnes-aigc/m03_videos-watermarks/water-cgt-20260122113851-845ws.mp4"
    },
]

GEN_COMMENTARY_URL = "http://127.0.0.1:8801/api/initiative/event"

class TestCallGeminiCompareAndComment:
    """测试 call_gemini_compare_and_comment 函数"""

    @pytest.mark.asyncio
    async def test_commentary_api(self):
        """测试成功生成图片点评的场景"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "event_type": "commentary",
                "event_dict": {
                    "user_upload_url": test_case["case6"]["user_upload_url"],
                    "s3_url": test_case["case6"]["s3_url"],
                    "message_id": "1769067770051-3a019851",
                    "group_id": "1768983883283-35e65dca",
                    "is_template": True,
                    "language_code": "zh"
                }
            }

            response = await client.post(
                GEN_COMMENTARY_URL,
                json=payload
            )
        
            rst_json = response.json()
            data = rst_json.get("data", {})
            print(f"生成的点评内容greeting: {data.get('greeting')}")
            print(f"语种language_code: {data.get('language_code')}")
            print(f"是否降级fallback: {data.get('fallback')}")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_commentary_api_batch(self):
        """批量测试：并发发送 5 组 test_case 数据并统一输出结果"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            tasks = []
            for case_key, case_value in test_case.items():
                payload = {
                    "event_type": "commentary",
                    "event_dict": {
                        "user_upload_url": case_value["user_upload_url"],
                        "s3_url": case_value["s3_url"],
                        "message_id": "1769067770051-3a019851",
                        "group_id": "1768983883283-35e65dca",
                        "is_template": True,
                        "language_code": random.choice(["zh", "en", "jp"])
                    }
                }
                # 将协程对象加入列表，不立即 await
                tasks.append(client.post(GEN_COMMENTARY_URL, json=payload))
            
            print(f"\n开始批量发送 {len(tasks)} 个请求...")
            # 统一等待所有请求完成
            responses = await asyncio.gather(*tasks)
            
            print("\n" + "="*50)
            print("批量测试结果汇总：")
            print("="*50)
            
            for idx, response in enumerate(responses):
                case_name = list(test_case.keys())[idx]
                print(f"\n[案例: {case_name}]")
                print(f"状态码: {response.status_code}")
                
                try:
                    rst_json = response.json()
                    data = rst_json.get("data", {})
                    print(f"生成的点评内容: {data.get('greeting')}")
                    print(f"语种: {data.get('language_code')}")
                    print(f"是否降级: {data.get('fallback')}")
                    
                    assert response.status_code == 200
                    assert rst_json.get("code") == 200
                except Exception as e:
                    print(f"处理响应时出错: {str(e)}")
                    print(f"原始响应: {response.text}")

            print("="*50)


    @pytest.mark.asyncio
    async def test_commentary_api_multi_rounds(self):
        """多轮次测试：连续发起多轮批量点评请求，并比较结果与性能指标"""
        rounds = 5  # 测试轮数
        async with httpx.AsyncClient(timeout=60.0*rounds) as client:
            all_round_results = {} # {round_num: {case_name: {"greeting": str, "latency": float}}}
            total_start_time = time.perf_counter()
            
            for r in range(1, rounds + 1):
                print(f"\n>>> 开始第 {r} 轮测试...")
                round_start_time = time.perf_counter()
                tasks = []
                case_names = list(test_case.keys())
                
                async def timed_post(name, payload):
                    start = time.perf_counter()
                    try:
                        resp = await client.post(GEN_COMMENTARY_URL, json=payload)
                        latency = time.perf_counter() - start
                        return name, resp, latency
                    except Exception as e:
                        latency = time.perf_counter() - start
                        return name, e, latency

                for key in case_names:
                    payload = {
                        "event_type": "commentary",
                        "event_dict": {
                            "user_upload_url": test_case[key]["user_upload_url"],
                            "s3_url": test_case[key]["s3_url"],
                            "message_id": "1769067770051-3a019851",
                            "group_id": "1768983883283-35e65dca",
                            "is_template": True,
                            "language_code": "zh"
                        }
                    }
                    tasks.append(timed_post(key, payload))
                
                results = await asyncio.gather(*tasks)
                round_data = {}
                round_latencies = []
                
                for case_name, resp, latency in results:
                    round_latencies.append(latency)
                    if isinstance(resp, httpx.Response):
                        if resp.status_code == 200:
                            greeting = resp.json().get("data", {}).get("greeting", "N/A")
                            round_data[case_name] = {"greeting": greeting, "latency": latency}
                        else:
                            round_data[case_name] = {"greeting": f"Error: {resp.status_code}", "latency": latency}
                    else:
                        round_data[case_name] = {"greeting": f"Exception: {str(resp)}", "latency": latency}
                
                all_round_results[r] = round_data
                round_duration = time.perf_counter() - round_start_time
                print(f"第 {r} 轮完成，耗时: {round_duration:.2f}s, 平均请求延迟: {sum(round_latencies)/len(round_latencies):.2f}s")
                
                if r < rounds:
                    await asyncio.sleep(2) # 轮次间隔
            
            total_duration = time.perf_counter() - total_start_time
            
            # 结果比较与性能汇总
            print("\n" + "="*80)
            print(f"多轮次测试汇总分析 (总轮数: {rounds}, 总耗时: {total_duration:.2f}s)")
            print("="*80)
            
            all_latencies = []
            case_names = list(test_case.keys())
            
            for r in range(1, rounds + 1):
                print(f"\n[第 {r} 轮详情]")
                round_data = all_round_results[r]
                round_latencies = []
                for name in case_names:
                    res = round_data[name]
                    greeting = res["greeting"]
                    latency = res["latency"]
                    round_latencies.append(latency)
                    all_latencies.append(latency)
                    print(f"  案例: {name:<10} | 延迟={latency:.2f}s | 内容={greeting}")
                
                print(f"  --> 轮次概况: 平均延迟={sum(round_latencies)/len(round_latencies):.2f}s | 并发总耗时统计见上文")
            
            print("\n" + "="*80)
            print("整体性能统计 (Across All Rounds):")
            if all_latencies:
                print(f"  总请求数: {len(all_latencies)}")
                print(f"  平均响应时间: {sum(all_latencies)/len(all_latencies):.2f}s")
                print(f"  最小响应时间: {min(all_latencies):.2f}s")
                print(f"  最大响应时间: {max(all_latencies):.2f}s")
                print(f"  吞吐量: {len(all_latencies)/total_duration:.2f} req/s")
            print("="*80)


    @pytest.mark.asyncio
    async def test_invalid_input_empty_urls(self):
        """测试素材图片列表为空的情况"""
        with pytest.raises(ValueError, match="image_urls 不能为空"):
            await call_gemini_compare_and_comment(
                image_urls=[],
                generated_url="http://example.com/gen.jpg",
                generated_type="image"
            )

    @pytest.mark.asyncio
    async def test_invalid_generated_type(self):
        """测试无效的生成类型"""
        with pytest.raises(ValueError, match="generated_type 必须是 'image' 或 'video'"):
            await call_gemini_compare_and_comment(
                image_urls=["http://example.com/src.jpg"],
                generated_url="http://example.com/gen.jpg",
                generated_type="audio"  # Invalid
            )

    @pytest.mark.asyncio
    async def test_http_connect_error(self):
        """测试 HTTP 连接错误"""
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection failed")):
            with pytest.raises(RuntimeError, match="连接失败"):
                await call_gemini_compare_and_comment(
                    image_urls=["http://example.com/src.jpg"],
                    generated_url="http://example.com/gen.jpg",
                    generated_type="image"
                )

    @pytest.mark.asyncio
    async def test_http_timeout_error(self):
        """测试 HTTP 请求超时"""
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
            with pytest.raises(RuntimeError, match="请求超时"):
                await call_gemini_compare_and_comment(
                    image_urls=["http://example.com/src.jpg"],
                    generated_url="http://example.com/gen.jpg",
                    generated_type="image"
                )

    @pytest.mark.asyncio
    async def test_http_status_not_200(self):
        """测试 OneRouter 返回非 200 状态码"""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            with pytest.raises(RuntimeError, match="OneRouter HTTP 500"):
                await call_gemini_compare_and_comment(
                    image_urls=["http://example.com/src.jpg"],
                    generated_url="http://example.com/gen.jpg",
                    generated_type="image"
                )

    @pytest.mark.asyncio
    async def test_onerouter_error_response(self):
        """测试 OneRouter 返回带有 error 字段的响应"""
        mock_response_data = {"error": "Invalid API Key"}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            with pytest.raises(RuntimeError, match="OneRouter error: Invalid API Key"):
                await call_gemini_compare_and_comment(
                    image_urls=["http://example.com/src.jpg"],
                    generated_url="http://example.com/gen.jpg",
                    generated_type="image"
                )

    @pytest.mark.asyncio
    async def test_invalid_response_schema(self):
        """测试响应结构不符合预期"""
        mock_response_data = {"choices": []}  # Missing message
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            with pytest.raises(RuntimeError, match="Invalid response schema"):
                await call_gemini_compare_and_comment(
                    image_urls=["http://example.com/src.jpg"],
                    generated_url="http://example.com/gen.jpg",
                    generated_type="image"
                )

    @pytest.mark.asyncio
    async def test_fallback_text_hit(self):
        """测试命中 OneRouter fallback 模板文本"""
        fallback_texts = [
            "The generated result is a nice picture.",
            "The model produced an error while processing.",
            "I'm sorry, I cannot help with that.",
            "I cannot fulfill this request."
        ]
        
        for text in fallback_texts:
            mock_response_data = {
                "choices": [{"message": {"content": text}}]
            }
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response_data
            
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp
                with pytest.raises(RuntimeError, match="OneRouter fallback text hit"):
                    await call_gemini_compare_and_comment(
                        image_urls=["http://example.com/src.jpg"],
                        generated_url="http://example.com/gen.jpg",
                        generated_type="image"
                    )

    @pytest.mark.asyncio
    async def test_empty_model_output(self):
        """测试模型输出为空的情况"""
        mock_response_data = {
            "choices": [{"message": {"content": "   "}}]
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            with pytest.raises(RuntimeError, match="Empty model output"):
                await call_gemini_compare_and_comment(
                    image_urls=["http://example.com/src.jpg"],
                    generated_url="http://example.com/gen.jpg",
                    generated_type="image"
                )

    @pytest.mark.asyncio
    async def test_language_length_rule_cjk(self):
        """测试 CJK 语言下的长度规则应用"""
        image_urls = ["http://example.com/source.jpg"]
        generated_url = "http://example.com/gen.jpg"
        generated_type = "image"
        
        mock_response_data = {
            "choices": [{"message": {"content": "模型回复"}}]
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            # 传入 zh-CN，应该识别为 CJK
            await call_gemini_compare_and_comment(
                image_urls=image_urls,
                generated_url=generated_url,
                generated_type=generated_type,
                language_code="zh-CN"
            )
            
            # 获取发送给 httpx 的 payload
            args, kwargs = mock_post.call_args
            payload = kwargs["json"]
            prompt_in_payload = payload["messages"][0]["content"][-1]["text"]
            
            # 验证 prompt 中包含 CJK 长度规则和标准化后的语言代码
            assert "Comments length: 50-80 Chinese characters" in prompt_in_payload
            assert "Write the comment in zh ONLY" in prompt_in_payload

    @pytest.mark.asyncio
    async def test_language_length_rule_non_cjk(self):
        """测试非 CJK 语言下的长度规则应用"""
        image_urls = ["http://example.com/source.jpg"]
        generated_url = "http://example.com/gen.jpg"
        generated_type = "image"
        
        mock_response_data = {
            "choices": [{"message": {"content": "Model response"}}]
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            # 传入 en-US
            await call_gemini_compare_and_comment(
                image_urls=image_urls,
                generated_url=generated_url,
                generated_type=generated_type,
                language_code="en-US"
            )
            
            args, kwargs = mock_post.call_args
            payload = kwargs["json"]
            prompt_in_payload = payload["messages"][0]["content"][-1]["text"]
            
            assert "Comments length: 30-60 words" in prompt_in_payload
            assert "Write the comment in en ONLY" in prompt_in_payload

