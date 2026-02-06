# 日志模块详细说明

### 概述

本项目采用 **Structlog + ContextVars** 的现代化日志方案，这是 FastAPI 社区最成熟的日志解决方案。

**核心特性：**
- ✅ **结构化日志**：JSON 格式输出，便于日志分析系统解析
- ✅ **请求追踪**：自动生成唯一 `request_id`，追踪整个请求生命周期
- ✅ **协程安全**：基于 ContextVars 实现，高并发场景下上下文完全隔离
- ✅ **自动上下文注入**：只在 ContextVars 中存储 `request_id`，其他业务字段作为参数传递
- ✅ **开发友好**：控制台彩色输出，文件 JSON 格式

### 设计原则

**ContextVars 只存储不变的请求标识：**
- ✅ **存储：** `request_id` - 在整个 HTTP 请求生命周期中唯一且不变
- ❌ **不存储：** `event_type`, `group_id`, `user_name`, `message_id` - 这些字段在请求中可能变化

### 基础使用

#### 1. 结构化日志（推荐）

```python
from utils.logger import logger

# ✅ 推荐：结构化参数
logger.info(
    "LLM 生成完成",
    event_type="greet",
    group_id=group_id,
    user_name=user_name,
    model="gemini-2.5-flash",
    tokens=150,
    duration_ms=892,
    success=True,
)

# ❌ 不推荐：字符串拼接
logger.info(f"LLM 生成完成 - model: {model}, tokens: {tokens}")
```

#### 2. 自动请求追踪

中间件会自动为每个请求生成 `request_id`，所有日志自动包含：

```python
# 无需手动传递 request_id
logger.info("处理开始", event_type="greet")  # 自动包含 request_id
await some_service()                         # 内部日志也有相同 request_id
logger.info("处理完成", event_type="greet")  # 仍然是同一个 request_id
```

### 日志输出格式

**控制台输出（彩色，开发友好）：**
```
2026-01-10T15:30:45.123Z [info] LLM问候语生成开始
  request_id=a1b2c3d4 event_type=greet group_id=group_123 has_user_name=True
```

**文件输出（JSON，便于解析）：**
```json
{
  "event": "LLM问候语生成开始",
  "timestamp": "2026-01-10T15:30:45.123456Z",
  "level": "info",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "event_type": "greet",
  "group_id": "group_123",
  "user_name": "Alice",
  "has_user_name": true,
  "has_contexts": true,
  "filename": "greeting_service.py",
  "func_name": "generate_greeting",
  "lineno": 213
}
```

### 日志查询

#### 使用 jq 查询 JSON 日志

```bash
# 查询特定请求的所有日志
cat event_handler.log | jq 'select(.request_id == "a1b2c3d4-e5f6-7890")'

# 查询特定用户的所有操作
cat event_handler.log | jq 'select(.user_name == "Alice")'

# 查询所有错误日志
cat event_handler.log | jq 'select(.level == "error")'

# 统计不同 event_type 的数量
cat event_handler.log | jq -s 'group_by(.event_type) | map({type: .[0].event_type, count: length})'

# 查询响应时间超过 1 秒的请求
cat event_handler.log | jq 'select(.process_time_ms > 1000)'
```

#### 使用内置分析工具

```bash
python analyze_logs.py
```

**输出示例：**
```
总日志条数: 156
日志级别分布:
  INFO      :   145
  WARNING   :     8
  ERROR     :     3

event_type 分布:
  greet          :    89
  commentary     :    56

独立请求数量: 78
```

### 高级用法

#### 手动设置上下文（后台任务）

```python
from utils.logger import set_request_context, clear_request_context, logger

# 设置上下文（只设置 request_id）
request_id = set_request_context()

try:
    # 业务字段作为参数传递
    logger.info(
        "定时任务开始",
        event_type="scheduled_task",
        task_name="cleanup",
    )
    # 执行任务...
finally:
    # 清理上下文（重要！）
    clear_request_context()
```

### 最佳实践

1. **只在 ContextVars 中存储 request_id**
   - 不要试图存储业务字段，它们会在请求中变化

2. **使用结构化日志格式**
   ```python
   # ✅ 推荐
   logger.info("操作完成", user_id=123, duration_ms=45)
   
   # ❌ 不推荐
   logger.info(f"操作完成 - user: {user_id}, duration: {duration_ms}ms")
   ```

3. **避免 debug 级别日志**
   - 生产环境使用 INFO/WARNING/ERROR
   - debug 日志应该在开发完成后移除或改为 info

4. **保持字段名一致性**
   - 统一使用 `user_name`，不要混用 `username`
   - 统一使用 `group_id`，不要混用 `groupId`

5. **敏感信息脱敏**
   ```python
   # ❌ 不推荐
   logger.info("用户认证", password=password)
   
   # ✅ 推荐
   logger.info("用户认证", user_id=user_id, has_password=bool(password))
   ```


### 测试

运行日志系统测试：

```bash
python -m tests.unit.test_structlog
```

### 架构设计

```
请求进入
    ↓
LogContextMiddleware (中间件)
    - 生成唯一 request_id
    - 注入 ContextVars
    ↓
路由处理器 (event_handler)
    - logger.info(...)
    - 自动包含 request_id
    - 业务字段作为参数传递
    ↓
业务服务层 (greeting_service, llm_service)
    - 所有 logger 自动包含相同的 request_id
    ↓
Structlog 处理链
    - 添加时间戳
    - 添加调用位置 (文件/函数/行号)
    - 注入 ContextVars 上下文
    - 格式化输出 (控制台：彩色 / 文件：JSON)
    ↓
日志输出
    - 控制台：开发友好的彩色格式
    - 文件：结构化 JSON 格式
```

### 设计优势

#### 1. 灵活性

业务字段作为参数传递，支持在同一请求中动态变化：

```python
# 同一请求中处理多个用户
request_id = set_request_context()

logger.info("处理用户1", user_name="Alice", group_id="group_1")
await process_user("Alice", "group_1")

logger.info("处理用户2", user_name="Bob", group_id="group_2")
await process_user("Bob", "group_2")

# 两条日志的 request_id 相同，但 user_name 和 group_id 不同
```

#### 2. 避免状态泄漏

```python
# ❌ 错误示例：业务字段存储在 ContextVars
set_request_context(user_name="Alice")
logger.info("处理Alice")  # ✓ user_name=Alice

# 业务逻辑切换到处理Bob，但忘记更新 ContextVars
await process_user("Bob")
logger.info("处理用户")  # ✗ user_name 仍然是 Alice！

# ✅ 正确示例：业务字段作为参数传递
set_request_context()  # 只设置 request_id
logger.info("处理Alice", user_name="Alice")
logger.info("处理Bob", user_name="Bob")  # 各自独立，不会混淆
```

### 日志追踪示例

假设两个并发请求：

**请求 1（greet 事件）：**
```json
{"request_id": "req-001", "event_type": "greet", "group_id": "group_A", "event": "请求开始"}
{"request_id": "req-001", "event_type": "greet", "group_id": "group_A", "event": "取回群组上下文"}
{"request_id": "req-001", "event_type": "greet", "group_id": "group_A", "event": "LLM生成完成"}
{"request_id": "req-001", "event_type": "greet", "group_id": "group_A", "event": "请求完成"}
```

**请求 2（commentary 事件）：**
```json
{"request_id": "req-002", "event_type": "commentary", "group_id": "group_B", "event": "请求开始"}
{"request_id": "req-002", "event_type": "commentary", "group_id": "group_B", "event": "LLM生成完成"}
{"request_id": "req-002", "event_type": "commentary", "group_id": "group_B", "event": "发送消息"}
{"request_id": "req-002", "event_type": "commentary", "group_id": "group_B", "event": "请求完成"}
```

即使并发执行，通过 `request_id` 可以完美分离和追踪每个请求的完整生命周期。

### 对比传统方案

| 特性 | 旧方案（asyncio.current_task） | 新方案（Structlog + ContextVars） |
|------|-------------------------------|----------------------------------|
| 协程追踪 | ✅ 可以追踪 Task ID | ✅ 请求级别追踪（更精准） |
| 请求隔离 | ❌ 无法区分不同请求 | ✅ 完全隔离 |
| 上下文信息 | ❌ 只有 Task ID | ✅ request_id + 业务字段（参数传递） |
| 日志格式 | ❌ 纯文本 | ✅ JSON（可解析） |
| 日志分析 | ❌ 困难 | ✅ 易于查询和统计 |
| 状态安全 | ❌ 容易泄漏 | ✅ 自动清理 |
| 性能 | 一般 | 优秀（Structlog 高度优化） |

