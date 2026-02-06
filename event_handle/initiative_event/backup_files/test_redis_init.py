"""
测试 Redis 初始化的线程安全和异步安全性
"""
import asyncio
import time
from storage import init_dao, get_dao, dao

async def test_concurrent_init():
    """测试并发初始化（异步安全测试）"""
    print("=" * 60)
    print("测试 1: 并发初始化测试（异步安全）")
    print("=" * 60)
    
    # 模拟多个协程同时调用 init_dao
    tasks = [init_dao() for _ in range(10)]
    start_time = time.time()
    results = await asyncio.gather(*tasks)
    end_time = time.time()
    
    # 检查所有返回的 dao 实例是否是同一个
    dao_ids = [id(result) for result in results]
    print(f"✅ 并发调用 10 次 init_dao()")
    print(f"⏱️  耗时: {end_time - start_time:.3f} 秒")
    print(f"🔍 DAO 实例 ID: {dao_ids[0]}")
    print(f"✅ 所有实例是否相同: {len(set(dao_ids)) == 1}")
    print()

async def test_get_dao_performance():
    """测试 get_dao 性能（避免重复初始化）"""
    print("=" * 60)
    print("测试 2: get_dao() 性能测试（避免重复初始化）")
    print("=" * 60)
    
    # 第一次调用
    start_time = time.time()
    dao1 = await get_dao()
    first_call_time = time.time() - start_time
    print(f"🔄 首次调用 get_dao(): {first_call_time:.3f} 秒")
    
    # 后续调用应该非常快（仅健康检查）
    times = []
    for i in range(5):
        start_time = time.time()
        dao_n = await get_dao()
        call_time = time.time() - start_time
        times.append(call_time)
        print(f"⚡ 第 {i+2} 次调用 get_dao(): {call_time:.6f} 秒")
    
    avg_time = sum(times) / len(times)
    print(f"📊 后续调用平均耗时: {avg_time:.6f} 秒")
    print(f"✅ 所有实例是否相同: {id(dao1) == id(dao)}")
    print()

async def test_redis_connection():
    """测试 Redis 连接健康检查"""
    print("=" * 60)
    print("测试 3: Redis 连接健康检查")
    print("=" * 60)
    
    current_dao = await get_dao()
    
    # 测试 ping
    try:
        await current_dao.redis.ping()
        print("✅ Redis 连接正常")
    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
    
    # 测试 ensure_redis_connection
    try:
        await current_dao.ensure_redis_connection()
        print("✅ ensure_redis_connection() 执行成功")
    except Exception as e:
        print(f"❌ ensure_redis_connection() 失败: {e}")
    
    print()

async def test_concurrent_get_dao():
    """测试并发 get_dao 调用"""
    print("=" * 60)
    print("测试 4: 并发 get_dao() 调用（循环调用模拟）")
    print("=" * 60)
    
    # 模拟 20 次并发调用
    tasks = [get_dao() for _ in range(20)]
    start_time = time.time()
    results = await asyncio.gather(*tasks)
    end_time = time.time()
    
    dao_ids = [id(result) for result in results]
    print(f"✅ 并发调用 20 次 get_dao()")
    print(f"⏱️  耗时: {end_time - start_time:.3f} 秒")
    print(f"✅ 所有实例是否相同: {len(set(dao_ids)) == 1}")
    print(f"✅ 单例模式验证: {'通过' if len(set(dao_ids)) == 1 else '失败'}")
    print()

async def main():
    print("\n🚀 开始测试 Redis 初始化优化\n")
    
    try:
        # 测试 1: 并发初始化
        await test_concurrent_init()
        
        # 测试 2: get_dao 性能
        await test_get_dao_performance()
        
        # 测试 3: 连接健康检查
        await test_redis_connection()
        
        # 测试 4: 并发 get_dao
        await test_concurrent_get_dao()
        
        print("=" * 60)
        print("🎉 所有测试完成！")
        print("=" * 60)
        
        # 清理
        if dao:
            await dao.close_redis()
            print("✅ Redis 连接已关闭")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
