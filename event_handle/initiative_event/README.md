# Event Handler API - 重构后项目说明

## 项目概述

Event Handler API 是一个基于 FastAPI 的事件处理服务，支持点赞（filter）、问候语生成（greet）和点评（commentary）等事件类型。

## 项目结构

```
initiative_event/
├── app/                           # 应用核心目录
│   ├── __init__.py               # 应用初始化
│   ├── main.py                   # FastAPI 应用实例创建与生命周期管理
│   └── routers/                  # 路由模块目录
│       ├── __init__.py
│       ├── event/                # 事件处理路由
│       │   ├── __init__.py
│       │   ├── event_handler.py  # 事件处理路由端点
│       │   └── schemas.py        # 事件相关 Pydantic 模型
│       └── interact/             # 互动处理路由
│           ├── __init__.py
│           ├── interact_handler.py  # 互动处理路由端点
│           ├── interact_utils.py    # 互动工具函数
│           └── schemas.py           # 互动相关 Pydantic 模型
├── services/                      # 业务服务层
│   ├── __init__.py
│   ├── greeting_service.py       # 问候语生成服务
│   ├── llm_service.py            # LLM 调用服务
│   └── external_api_service.py   # 外部 API 调用服务（点赞、发消息等）
├── storage/                       # 数据存储层
│   ├── __init__.py
│   └── redis_helper.py           # Redis 助手
├── utils/                         # 工具函数目录
│   ├── __init__.py
│   ├── language_utils.py         # 语言代码标准化、语言识别
│   ├── prompt_utils.py           # Prompt 构建、模板管理
│   └── logger.py                 # 日志工具
├── const.py                       # 全局常量定义
├── prompts/                       # Prompt 配置文件
│   ├── morning_prompts.json
│   └── evening_prompts.json
├── tests/                         # 测试目录
│   ├── __init__.py
│   ├── unit/                     # 单元测试
│   │   ├── test_redis_helper.py
│   │   ├── test_interact_handler.py  # 互动处理测试
│   │   └── test_interact_utils.py    # 互动工具函数测试
│   ├── integration/              # 集成测试
│   └── fixtures/                 # 测试固定装置
├── run.py                         # 应用启动入口
└── .env                          # 环境变量配置文件
```

## 快速开始

### 1. 安装依赖

```bash
pip install structlog python-json-logger fastapi uvicorn openai httpx redis python-dotenv pydantic
```

### 2. 配置环境变量

编辑 `.env` 文件，配置以下环境变量：

```env
# OpenAI 配置
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://app.onerouter.pro/v1
LLM_CHAT_CHECK_MODEL=gemini-2.5-flash
LLM_GREET_MODEL=gemini-2.5-flash

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# API 地址配置
LIKE_API_URL=http://192.168.10.20:8093/api/group_chat/message_vote_by_agnes
SEND_MESSAGE_API_URL=http://192.168.10.20:8089/api/group_chat/send_message

# 应用配置
APP_HOST=0.0.0.0
APP_PORT=8800

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=event_handler.log
```

### 3. 启动应用

```bash
python hello_api.py
```

或使用 uvicorn 直接启动：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8800
```

### 4. 访问 API 文档

启动后访问：
- Swagger UI: http://localhost:8800/docs
- ReDoc: http://localhost:8800/redoc

## API 端点

### 事件处理接口

#### POST /api/initiative/event

处理不同类型的事件。

#### Greet 事件（问候语生成）

```json
{
  "event_type": "greet",
  "event_dict": {
    "greet_type": "good_m",
    "user_name": "张三",
    "language_code": "zh"
  }
}
```

#### Commentary 事件（点评）

```json
{
  "event_type": "commentary",
  "event_dict": {
    "message_id": "msg_123",
    "group_id": "group_456",
    "prompt": "这是一条需要点评的消息",
    "language_code": "zh"
  }
}
```

---

### 互动处理接口

互动接口用于处理群聊中的消息互动判断和点赞操作。详细文档请参考：[互动接口文档](docs/interact_api.md)

#### POST /api/initiative/interaction

处理消息互动判断，支持两种互动类型：

**Message 类型**（消息互动）:
```json
{
  "msg_type": "message",
  "msg_dict": {
    "message_id": "msg_123",
    "group_id": "group_456",
    "contents": "@Agnes 你好棒!",
    "is_agnes": false
  }
}
```

**Others 类型**（其他互动）:
```json
{
  "msg_type": "others",
  "msg_dict": {
    "message_id": "msg_123",
    "group_id": "group_456"
  }
}
```

**核心功能**:
- 🤖 **LLM 情感分析**: 自动识别消息情感类型（积极/搞笑/惊讶/难过/生气/中性）
- 🎲 **概率控制**: 旁观者场景和 others 类型支持概率触发
- 👍 **智能点赞**: 根据情感类型和场景智能决定是否点赞
- 🔍 **场景区分**: 区分 @Agnes 和旁观者场景，采用不同策略

**业务逻辑**:
1. **Message 类型**:
   - 系统消息（is_agnes=true）→ 跳过
   - LLM 分析情感 → 中性消息（标签6）→ 跳过
   - @Agnes 场景 → 直接点赞（不启用概率）
   - 旁观者场景 → 80% 概率点赞

2. **Others 类型**:
   - 根据配置概率（LIKE_PROBABILITY）判断
   - 命中后随机选择 emoji (0-3) 点赞


## 日志系统

本项目采用 **Structlog + ContextVars** 的现代化日志方案，支持结构化日志、请求追踪和协程安全。

### 快速开始

#### 基本使用

```python
from utils.logger import logger

# ✅ 推荐：结构化参数
logger.info(
    "LLM 生成完成",
    event_type="greet",
    user_name=user_name,
    model="gemini-2.5-flash",
    tokens=150,
    success=True,
)

# ❌ 不推荐：字符串拼接
logger.info(f"LLM 生成完成 - model: {model}, tokens: {tokens}")
```

#### 自动请求追踪

中间件会自动为每个请求生成 `request_id`，无需手动传递：

```python
logger.info("处理开始", event_type="greet")  # 自动包含 request_id
await some_service()                         # 内部日志也有相同 request_id
logger.info("处理完成", event_type="greet")  # 仍然是同一个 request_id
```

### 日志查询

```bash
# 查询特定请求的所有日志
cat event_handler.log | jq 'select(.request_id == "a1b2c3d4-e5f6-7890")'

# 查询所有错误日志
cat event_handler.log | jq 'select(.level == "error")'
```

### 详细文档

更多高级用法、设计原则、架构说明等，请查看：
- **[日志模块详细文档](docs/log_module.md)** - 包含完整的设计原则、架构设计、最佳实践、日志分析方法等
- **[互动接口详细文档](docs/interact_api.md)** - 包含接口说明、业务逻辑、情感标签、测试用例等完整信息

## 测试

### 运行日志系统测试

```bash
python -m tests.unit.test_structlog
```

更多测试方法请参考 [日志模块详细文档](docs/log_module.md)。

### 运行 Redis 单元测试

```bash
python tests/unit/test_redis_helper.py
```

### 运行互动模块单元测试

```bash
# 测试互动处理路由
pytest tests/unit/test_interact_handler.py -v

# 测试互动工具函数
pytest tests/unit/test_interact_utils.py -v

# 运行所有互动模块测试
pytest tests/unit/test_interact*.py -v
```

## 重构改进点

### 1. 架构优化
- **分层架构**：采用经典的三层架构（路由层 → 服务层 → 数据层）
- **职责分离**：每个模块职责明确，符合单一职责原则
- **依赖注入**：通过配置文件管理依赖关系

### 2. 代码质量提升
- **类型注解**：所有函数参数、返回值均有类型注解
- **常量管理**：通过 const.py 集中管理所有硬编码常量
- **日志规范**：统一的日志配置和格式
- **文档完善**：每个模块、类、函数都有详细的文档字符串

### 3. 可维护性提升
- **工具函数复用**：语言处理、Prompt 构建等通用功能独立成工具模块
- **测试分类**：单元测试、集成测试分离管理
- **配置灵活**：支持环境变量配置，便于多环境部署

## 开发建议

### 添加新事件类型

1. 在 `app/routers/event/schemas.py` 中更新 `EventRequest` 的 `event_type`
2. 在 `app/routers/event/event_handler.py` 中添加新的事件处理逻辑
3. 如需新服务，在 `services/` 下创建对应服务模块

### 添加新工具函数

在 `utils/` 目录下创建新的工具模块，并在 `utils/__init__.py` 中导出。

### 添加新常量

在 `const.py` 中定义新常量，优先从环境变量读取。

## 注意事项

1. **环境变量优先级**：环境变量 > const.py 默认值
2. **Redis 连接**：应用启动时自动初始化，关闭时自动释放
3. **日志文件**：默认输出到 `event_handler.log`
4. **Python 版本**：建议使用 Python 3.9+

## 问题排查

### 导入错误

确保在项目根目录运行应用，或将项目根目录添加到 PYTHONPATH：

```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/initiative_event"
```

### Redis 连接失败

检查 Redis 服务是否启动，以及 `.env` 中的 Redis 配置是否正确。

### LLM 调用失败

检查 OpenAI API Key 是否正确，以及网络连接是否正常。

## 许可证

本项目仅供学习和内部使用。
