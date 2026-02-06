"""
问候语生成接口测试
"""
import asyncio
import httpx
import pytest
import time
import random
from typing import Dict, List, Tuple


group_ids = [
    "1767874290332-35b3ae35", 
    "1762158322961-31f96f22",
    "1767789521516-794acf3f",
    "1766996874650-f166cc17",
    "1766987339520-98477986",
    "1766921475863-3d059b4c",
    "1766891387218-d9d17085",
    "1766975573108-f5b59a33",
    "1766975023043-341a3aab"
]

infos = [
    {'return_code': 0, 'message': '获取群聊信息成功', 'group_id': '1767874290332-35b3ae35', 'user_id': None, 'has_context': False, 'context_info': {'focal_figure': None, 'topic_hot': '驴肉火烧', 'topic_ext': '河北', 'contexts_language': 'zh'}, 'contexts_str': None},
    {'return_code': 0, 'message': '获取群聊信息成功', 'group_id': '1762158322961-31f96f22', 'user_id': None, 'has_context': False, 'context_info': {'focal_figure': None, 'topic_hot': '海龟汤', 'topic_ext': None, 'contexts_language': 'zh'}, 'contexts_str': None},
    {'return_code': 0, 'message': '获取群聊信息成功', 'group_id': '1766996874650-f166cc17', 'user_id': None, 'has_context': False, 'context_info': {'focal_figure': None, 'topic_hot': '询问年龄', 'topic_ext': '要求表演', 'contexts_language': 'zh'}, 'contexts_str': None},
    {'return_code': 0, 'message': '获取群聊信息成功', 'group_id': '1766987339520-98477986', 'user_id': None, 'has_context': False, 'context_info': {'focal_figure': '特朗普', 'topic_hot': '特朗普', 'topic_ext': None, 'contexts_language': 'zh'}, 'contexts_str': None},
    {'return_code': 0, 'message': '获取群聊信息成功', 'group_id': '1766921475863-3d059b4c', 'user_id': None, 'has_context': False, 'context_info': {'focal_figure': '杨瀚森', 'topic_hot': '杨瀚森', 'topic_ext': '比赛', 'contexts_language': 'zh'}, 'contexts_str': None},
    {'return_code': 0, 'message': '获取群聊信息成功', 'group_id': '1766921475863-3d059b4c', 'user_id': None, 'has_context': False, 'context_info': {'focal_figure': '杨瀚森', 'topic_hot': '杨瀚森', 'topic_ext': '比赛', 'contexts_language': 'zh'}, 'contexts_str': None},
    {'return_code': 0, 'message': '获取群聊信息成功', 'group_id': '1766891387218-d9d17085', 'user_id': None, 'has_context': False, 'context_info': {'focal_figure': None, 'topic_hot': '新闻', 'topic_ext': '世界战争', 'contexts_language': 'zh'}, 'contexts_str': None},
    {'return_code': 0, 'message': '获取群聊信息成功', 'group_id': '1766975573108-f5b59a33', 'user_id': None, 'has_context': False, 'context_info': {'focal_figure': '奥巴马', 'topic_hot': '奥巴马', 'topic_ext': None, 'contexts_language': 'zh'}, 'contexts_str': None},
    {'return_code': 0, 'message': '获取群聊信息成功', 'group_id': '1766975023043-341a3aab', 'user_id': None, 'has_context': False, 'context_info': {'focal_figure': None, 'topic_hot': '古诗', 'topic_ext': None, 'contexts_language': 'zh'}, 'contexts_str': None},
]

meta_infos = {
    '1767874290332-35b3ae35': {'focal_figure': None, 'topic_hot': '驴肉火烧', 'topic_ext': '河北', 'contexts_language': 'zh'},
    '1762158322961-31f96f22': {'focal_figure': None, 'topic_hot': '海龟汤', 'topic_ext': None, 'contexts_language': 'zh'},
    '1766996874650-f166cc17': {'focal_figure': None, 'topic_hot': '询问年龄', 'topic_ext': '要求表演', 'contexts_language': 'zh'},
    '1766987339520-98477986': {'focal_figure': '特朗普', 'topic_hot': '特朗普', 'topic_ext': None, 'contexts_language': 'zh'},
    '1766921475863-3d059b4c': {'focal_figure': '杨瀚森', 'topic_hot': '杨瀚森', 'topic_ext': '比赛', 'contexts_language': 'zh'},
    '1766891387218-d9d17085': {'focal_figure': None, 'topic_hot': '新闻', 'topic_ext': '世界战争', 'contexts_language': 'zh'},
    '1766975573108-f5b59a33': {'focal_figure': '奥巴马', 'topic_hot': '奥巴马', 'topic_ext': None, 'contexts_language': 'zh'},
    '1766975023043-341a3aab': {'focal_figure': None, 'topic_hot': '古诗', 'topic_ext': None, 'contexts_language': 'zh'},
    '1767789521516-794acf3f': {'focal_figure': None, 'topic_hot': None, 'topic_ext': None, 'contexts_language': None}
    }

GET_GREET_URL = "http://127.0.0.1:8801/api/initiative/event"

GET_CONTEXT_INFO_URL = "http://127.0.0.1:8001/api/v1/memories/contexts/infos"





async def fetch_context_info(group_id: str, client: httpx.AsyncClient):
    """异步获取单个群聊的上下文信息"""
    try:
        response = await client.get(
            GET_CONTEXT_INFO_URL,
            params={"group_id": group_id}
        )
        return group_id, response.json()
    except Exception as e:
        return group_id, {"error": str(e)}


async def fetch_all_contexts():
    """异步获取所有群聊的上下文信息"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = []
        for group_id in group_ids:
            # 每隔10ms发送一个请求
            tasks.append(fetch_context_info(group_id, client))
            await asyncio.sleep(0.01)  # 10ms
        
        # 统一等待所有请求完成
        results = await asyncio.gather(*tasks)
        return results


# ==================== 压力测试 ====================

@pytest.mark.asyncio
class TestStressContextAPI:
    """上下文信息获取接口压力测试"""

    async def test_fetch_all_contexts_stress(self):
        """压力测试：并发获取所有群聊的上下文信息"""
        print("\n========== 开始压力测试 ==========")
        print(f"测试目标：{GET_CONTEXT_INFO_URL}")
        print(f"群组数量：{len(group_ids)}")
        print(f"请求间隔：10ms")
        print("="*40)
        
        # 统计信息
        success_count = 0
        error_count = 0
        response_times = []
        
        # 记录开始时间
        start_time = time.time()
        
        # 执行请求
        try:
            results = await fetch_all_contexts()
            
            # 分析结果
            for group_id, data in results:
                print(f"\n{'='*60}")
                print(f"群组ID: {group_id}")
                print(f"返回结果: {data}")
                print(f"{'='*60}")
                
                if "error" in data:
                    error_count += 1
                    print(f"❌ 状态: 请求失败")
                else:
                    success_count += 1
                    print(f"✅ 状态: 请求成功")
            
        except Exception as e:
            print(f"❌ 测试执行异常: {str(e)}")
            raise
        
        # 记录结束时间
        end_time = time.time()
        total_time = end_time - start_time
        
        # 输出统计信息
        print("\n========== 压力测试结果 ==========")
        print(f"总请求数：{len(group_ids)}")
        print(f"成功数：{success_count}")
        print(f"失败数：{error_count}")
        print(f"成功率：{(success_count / len(group_ids) * 100):.2f}%")
        print(f"总耗时：{total_time:.3f}秒")
        print(f"平均响应时间：{(total_time / len(group_ids)):.3f}秒/请求")
        print(f"QPS：{(len(group_ids) / total_time):.2f} 请求/秒")
        print("="*40)
        
        # 断言：至少80%的请求应该成功
        assert success_count / len(group_ids) >= 0.8, \
            f"成功率过低：{success_count}/{len(group_ids)}"

    async def test_multiple_rounds_stress(self):
        """多轮压力测试：连续发起多轮请求"""
        rounds = 3  # 测试轮数
        print(f"\n========== 开始多轮压力测试（{rounds}轮）==========")
        
        total_success = 0
        total_error = 0
        round_times = []
        
        for round_num in range(1, rounds + 1):
            print(f"\n--- 第 {round_num} 轮测试 ---")
            round_start = time.time()
            
            results = await fetch_all_contexts()
            
            # 打印每轮的详细结果
            for group_id, data in results:
                status = "失败" if "error" in data else "成功"
                print(f"  [{status}] 群组 {group_id}: {data}")
            
            success = sum(1 for _, data in results if "error" not in data)
            error = sum(1 for _, data in results if "error" in data)
            
            total_success += success
            total_error += error
            
            round_time = time.time() - round_start
            round_times.append(round_time)
            
            print(f"第 {round_num} 轮：成功 {success}, 失败 {error}, 耗时 {round_time:.3f}秒")
            
            # 每轮之间间隔1秒
            if round_num < rounds:
                await asyncio.sleep(1)
        
        # 输出汇总统计
        print("\n========== 多轮测试汇总 ==========")
        print(f"总轮数：{rounds}")
        print(f"总请求数：{rounds * len(group_ids)}")
        print(f"总成功数：{total_success}")
        print(f"总失败数：{total_error}")
        print(f"整体成功率：{(total_success / (rounds * len(group_ids)) * 100):.2f}%")
        print(f"平均每轮耗时：{(sum(round_times) / rounds):.3f}秒")
        print(f"最快一轮：{min(round_times):.3f}秒")
        print(f"最慢一轮：{max(round_times):.3f}秒")
        print("="*40)
        
        # 断言：整体成功率应该在80%以上
        overall_success_rate = total_success / (rounds * len(group_ids))
        assert overall_success_rate >= 0.8, \
            f"整体成功率过低：{overall_success_rate:.2%}"

    async def test_concurrent_clients_stress(self):
        """并发客户端压力测试：模拟多个客户端同时请求"""
        num_clients = 3  # 并发客户端数量
        print(f"\n========== 并发客户端压力测试（{num_clients}个客户端）==========")
        
        async def single_client_test(client_id: int):
            """单个客户端的测试"""
            print(f"客户端 {client_id} 开始测试")
            start = time.time()
            results = await fetch_all_contexts()
            elapsed = time.time() - start
            
            # 打印该客户端的详细结果
            print(f"\n客户端 {client_id} 请求结果：")
            for group_id, data in results:
                status = "失败" if "error" in data else "成功"
                print(f"  [{status}] 群组 {group_id}: {data}")
            
            success = sum(1 for _, data in results if "error" not in data)
            error = sum(1 for _, data in results if "error" in data)
            
            return {
                "client_id": client_id,
                "success": success,
                "error": error,
                "time": elapsed
            }
        
        # 并发执行多个客户端
        start_time = time.time()
        client_results = await asyncio.gather(
            *[single_client_test(i) for i in range(1, num_clients + 1)]
        )
        total_time = time.time() - start_time
        
        # 统计结果
        total_success = sum(r["success"] for r in client_results)
        total_error = sum(r["error"] for r in client_results)
        total_requests = num_clients * len(group_ids)
        
        print("\n========== 并发客户端测试结果 ==========")
        for result in client_results:
            print(f"客户端 {result['client_id']}: "
                  f"成功 {result['success']}, "
                  f"失败 {result['error']}, "
                  f"耗时 {result['time']:.3f}秒")
        
        print(f"\n并发总耗时：{total_time:.3f}秒")
        print(f"总请求数：{total_requests}")
        print(f"总成功数：{total_success}")
        print(f"总失败数：{total_error}")
        print(f"整体成功率：{(total_success / total_requests * 100):.2f}%")
        print(f"整体QPS：{(total_requests / total_time):.2f} 请求/秒")
        print("="*40)
        
        # 断言：成功率应该在70%以上（并发场景下降低要求）
        assert total_success / total_requests >= 0.7, \
            f"并发测试成功率过低：{total_success}/{total_requests}"

@pytest.mark.asyncio
async def test_greet_api_with_meta_infos():
    """基于 meta_infos 中的群聊信息，调用问候语生成接口"""
    async with httpx.AsyncClient(timeout=60.0) as client:

        tasks = []
        for group_id, context_info in meta_infos.items():
            language_code = context_info.get("contexts_language") or "en"

            topic_hot = [context_info.get("topic_hot", "")]
            if context_info.get("focal_figure"):
                topic_hot.append(context_info.get("focal_figure"))
            if context_info.get("topic_ext"):
                topic_hot.append(context_info.get("topic_ext"))
            topic = random.choice(topic_hot)

            # 固定用早安问候类型，参数要求简单
            greet_type = random.choice(["good_m", "good_n"])
            user_name = None           
            push_type = random.choice(["video", "news", "web_search"])

            payload = {
                "event_type": "greet",
                "event_dict": {
                    "greet_type": greet_type,
                    "user_name": user_name,
                    "language_code": language_code,
                    "group_id": group_id,
                    "topic": topic,       # 用上下文里的 topic_hot 作为主题
                    "push_type": push_type,   
                },
            }

            print("\n================ Greet 请求 =================")
            print(f"群组ID: {group_id}, 问候类型: {greet_type}, 用户名: {user_name}")
            print(f"语言: {language_code}, 主题: {topic}, 推送类型: {push_type}")
        
            # 批量下发请求
            tasks.append({
                "task": client.post(GET_GREET_URL, json=payload),
                "group_id": group_id,
                "context_info": context_info,
                "payload": payload,
            })

        # 统一等待所有请求完成
        print("\n================ 开始批量发送请求 =================")
        responses = await asyncio.gather(*[item["task"] for item in tasks], return_exceptions=True)
        print(f"收到 {len(responses)} 个响应\n")
        
        # 处理响应
        for idx, (task_info, response) in enumerate(zip(tasks, responses)):
            group_id = task_info["group_id"]
            payload = task_info["payload"]
        
            print(f"---------------- 接口响应 [{idx + 1}/{len(responses)}] ----------------")
            print(f"群组ID: {group_id}, 请求内容: {payload}")
                    
            if isinstance(response, Exception):
                print(f"请求异常: {response}")
                continue
                    
            print(f"状态码: {response.status_code}")
            try:
                resp_json = response.json()
            except Exception:
                resp_json = {"raw_text": response.text}
            print(f"响应内容: {resp_json.get('data')}")
            print("==========================================")
        
            # 基本断言：HTTP 和业务都成功，并且有问候语文本
            assert response.status_code == 200
            assert resp_json.get("code") == 200
            assert resp_json.get("data", {}).get("event_type") == "greet"
            greeting = resp_json.get("data", {}).get("greeting")
            assert isinstance(greeting, str) and greeting.strip()


@pytest.mark.asyncio
async def test_greet_api_multiple_rounds():
    """多轮次测试：基于 meta_infos 连续发起多轮问候语生成请求"""
    rounds = 3  # 测试轮数
    print(f"\n{'='*60}")
    print(f"开始多轮次问候语生成测试（{rounds}轮）")
    print(f"目标URL: {GET_GREET_URL}")
    print(f"群组数量: {len(meta_infos)}")
    print(f"{'='*60}")
    
    # 统计信息
    total_success = 0
    total_error = 0
    round_times = []
    round_results = []  # 记录每轮详细结果
    
    async with httpx.AsyncClient(timeout=60.0*rounds) as client:
        for round_num in range(1, rounds + 1):
            print(f"\n{'─'*60}")
            print(f"第 {round_num} 轮测试开始")
            print(f"{'─'*60}")
            
            round_start = time.time()
            
            # 构造本轮请求任务
            tasks = []
            for group_id, context_info in meta_infos.items():
                language_code = context_info.get("contexts_language") or "en"
                
                topic_hot = [context_info.get("topic_hot", "")]
                if context_info.get("focal_figure"):
                    topic_hot.append(context_info.get("focal_figure"))
                if context_info.get("topic_ext"):
                    topic_hot.append(context_info.get("topic_ext"))
                topic = random.choice(topic_hot)
                
                greet_type = random.choice(["good_m", "good_n"])
                user_name = None
                push_type = random.choice(["video", "news", "web_search"])
                
                payload = {
                    "event_type": "greet",
                    "event_dict": {
                        "greet_type": greet_type,
                        "user_name": user_name,
                        "language_code": language_code,
                        "group_id": group_id,
                        "topic": topic,
                        "push_type": push_type,
                    },
                }
                
                tasks.append({
                    "task": client.post(GET_GREET_URL, json=payload),
                    "group_id": group_id,
                    "payload": payload,
                })
            
            # 批量发送请求
            print(f"发送 {len(tasks)} 个请求...")
            responses = await asyncio.gather(
                *[item["task"] for item in tasks],
                return_exceptions=True
            )
            
            # 统计本轮结果
            round_success = 0
            round_error = 0
            round_detail = []
            
            for idx, (task_info, response) in enumerate(zip(tasks, responses)):
                group_id = task_info["group_id"]
                payload = task_info["payload"]
                
                if isinstance(response, Exception):
                    round_error += 1
                    status = "异常"
                    error_msg = str(response)
                    round_detail.append({
                        "group_id": group_id,
                        "status": status,
                        "error": error_msg
                    })
                    print(f"  [{idx+1}/{len(tasks)}] ❌ 群组 {group_id}: {error_msg}")
                else:
                    try:
                        resp_json = response.json()
                        if response.status_code == 200 and resp_json.get("code") == 200:
                            greeting = resp_json.get("data", {}).get("greeting", "")
                            if greeting and greeting.strip():
                                round_success += 1
                                status = "成功"
                                round_detail.append({
                                    "group_id": group_id,
                                    "status": status,
                                    "greeting": greeting[:70] + "..." if len(greeting) > 70 else greeting
                                })
                                print(f"  [{idx+1}/{len(tasks)}] ✅ 群组 {group_id}: {payload['event_dict']} : {greeting}")
                            else:
                                round_error += 1
                                status = "失败-无问候语"
                                round_detail.append({
                                    "group_id": group_id,
                                    "status": status,
                                    "response": resp_json
                                })
                                print(f"  [{idx+1}/{len(tasks)}] ⚠️  群组 {group_id}: 无问候语内容")
                        else:
                            round_error += 1
                            status = f"失败-{response.status_code}"
                            round_detail.append({
                                "group_id": group_id,
                                "status": status,
                                "response": resp_json
                            })
                            print(f"  [{idx+1}/{len(tasks)}] ❌ 群组 {group_id}: 状态码 {response.status_code}")

                    except Exception as e:
                        round_error += 1
                        status = "解析失败"
                        round_detail.append({
                            "group_id": group_id,
                            "status": status,
                            "error": str(e)
                        })
                        print(f"  [{idx+1}/{len(tasks)}] ❌ 群组 {group_id}: 解析异常 {str(e)}")

            total_success += round_success
            total_error += round_error
            
            round_time = time.time() - round_start
            round_times.append(round_time)
            
            round_results.append({
                "round": round_num,
                "success": round_success,
                "error": round_error,
                "time": round_time,
                "details": round_detail
            })
            
            print(f"\n第 {round_num} 轮结果：")
            print(f"  成功: {round_success}/{len(tasks)}")
            print(f"  失败: {round_error}/{len(tasks)}")
            print(f"  成功率: {(round_success / len(tasks) * 100):.2f}%")
            print(f"  耗时: {round_time:.3f}秒")
            print(f"  QPS: {(len(tasks) / round_time):.2f} 请求/秒")
            
            # 每轮之间间隔1秒
            if round_num < rounds:
                print(f"\n等待5秒后开始第 {round_num + 1} 轮...")
                await asyncio.sleep(5)
    
    # 输出汇总统计
    print(f"\n{'='*60}")
    print("多轮测试汇总统计")
    print(f"{'='*60}")
    print(f"总轮数: {rounds}")
    print(f"每轮群组数: {len(meta_infos)}")
    print(f"总请求数: {rounds * len(meta_infos)}")
    print(f"总成功数: {total_success}")
    print(f"总失败数: {total_error}")
    print(f"整体成功率: {(total_success / (rounds * len(meta_infos)) * 100):.2f}%")
    print(f"总耗时: {sum(round_times):.3f}秒")
    print(f"平均每轮耗时: {(sum(round_times) / rounds):.3f}秒")
    print(f"最快一轮: {min(round_times):.3f}秒")
    print(f"最慢一轮: {max(round_times):.3f}秒")
    print(f"平均QPS: {(rounds * len(meta_infos) / sum(round_times)):.2f} 请求/秒")
    print(f"{'='*60}")
    
    # 打印每轮成功率趋势
    print("\n各轮成功率趋势：")
    for result in round_results:
        success_rate = result["success"] / len(meta_infos) * 100
        bar_length = int(success_rate / 2)  # 按比例生成进度条
        bar = "█" * bar_length + "░" * (50 - bar_length)
        print(f"  第 {result['round']} 轮: {bar} {success_rate:.1f}%")
    
    # 断言：整体成功率应该在70%以上
    overall_success_rate = total_success / (rounds * len(meta_infos))
    assert overall_success_rate >= 0.7, \
        f"整体成功率过低：{overall_success_rate:.2%}（{total_success}/{rounds * len(meta_infos)}）"
    
    print("\n✅ 多轮次测试通过！")



# 如果需要单独运行压力测试
if __name__ == "__main__":
    # 运行单次压力测试
    asyncio.run(TestStressContextAPI().test_fetch_all_contexts_stress())
