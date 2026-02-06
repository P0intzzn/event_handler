"""
日志分析示例脚本

展示如何查询和分析结构化 JSON 日志
"""
import json
from collections import defaultdict
from pathlib import Path


def analyze_logs(log_file: str = "event_handler.log"):
    """分析日志文件"""
    
    if not Path(log_file).exists():
        print(f"日志文件不存在: {log_file}")
        return
    
    # 读取所有日志
    logs = []
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                log = json.loads(line.strip())
                logs.append(log)
            except json.JSONDecodeError:
                continue
    
    print(f"\n总日志条数: {len(logs)}")
    print("=" * 60)
    
    # 统计日志级别分布
    level_stats = defaultdict(int)
    for log in logs:
        level_stats[log.get('level', 'unknown')] += 1
    
    print("\n日志级别分布:")
    for level, count in sorted(level_stats.items()):
        print(f"  {level.upper():10s}: {count:5d}")
    
    # 统计 event_type 分布
    event_type_stats = defaultdict(int)
    for log in logs:
        event_type = log.get('event_type')
        if event_type:
            event_type_stats[event_type] += 1
    
    if event_type_stats:
        print("\nevent_type 分布:")
        for event_type, count in sorted(event_type_stats.items()):
            print(f"  {event_type:15s}: {count:5d}")
    
    # 统计 request_id 数量
    request_ids = set()
    for log in logs:
        request_id = log.get('request_id')
        if request_id:
            request_ids.add(request_id)
    
    print(f"\n独立请求数量: {len(request_ids)}")
    
    # 显示最近的几个请求的追踪
    print("\n最近请求追踪示例:")
    print("=" * 60)
    
    # 取最后几个不同的 request_id
    recent_requests = {}
    for log in reversed(logs):
        request_id = log.get('request_id')
        if request_id and request_id not in recent_requests:
            recent_requests[request_id] = []
        if request_id:
            recent_requests[request_id].insert(0, log)
        
        if len(recent_requests) >= 2:
            break
    
    for i, (request_id, request_logs) in enumerate(list(recent_requests.items())[:2], 1):
        print(f"\n请求 {i}: {request_id[:8]}...")
        first_log = request_logs[0]
        event_type = first_log.get('event_type', 'N/A')
        group_id = first_log.get('group_id', 'N/A')
        user_name = first_log.get('user_name', 'N/A')
        print(f"  - event_type: {event_type}")
        print(f"  - group_id: {group_id}")
        print(f"  - user_name: {user_name}")
        print(f"  - 日志条数: {len(request_logs)}")
        print(f"  - 事件流程:")
        for log in request_logs[:5]:  # 只显示前5条
            timestamp = log.get('timestamp', '')
            event = log.get('event', '')
            print(f"    {timestamp[-12:-1]} | {event}")


def search_by_request_id(request_id: str, log_file: str = "event_handler.log"):
    """根据 request_id 查找所有相关日志"""
    
    if not Path(log_file).exists():
        print(f"日志文件不存在: {log_file}")
        return
    
    print(f"\n查找 request_id: {request_id}")
    print("=" * 60)
    
    found_logs = []
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                log = json.loads(line.strip())
                if log.get('request_id') == request_id:
                    found_logs.append(log)
            except json.JSONDecodeError:
                continue
    
    if not found_logs:
        print("未找到相关日志")
        return
    
    print(f"找到 {len(found_logs)} 条日志:\n")
    for i, log in enumerate(found_logs, 1):
        timestamp = log.get('timestamp', '')
        level = log.get('level', 'unknown').upper()
        event = log.get('event', '')
        filename = log.get('filename', '')
        lineno = log.get('lineno', '')
        
        print(f"{i:2d}. [{level:7s}] {timestamp[-12:-1]} | {event}")
        print(f"    @ {filename}:{lineno}")
        
        # 显示额外的关键字段
        extra_fields = {k: v for k, v in log.items() 
                       if k not in ['event', 'level', 'logger', 'timestamp', 
                                   'request_id', 'filename', 'func_name', 'lineno']}
        if extra_fields:
            print(f"    额外信息: {extra_fields}")
        print()


if __name__ == "__main__":
    # 分析日志
    analyze_logs()
    
    # 如果想查找特定请求，取消下面的注释并替换 request_id
    # search_by_request_id("your-request-id-here")
