# Event 接口文档

## 概述

Event 路由模块负责处理各种主动性事件，包括问候语生成（greet）和点评内容生成（commentary）。该模块集成了 LLM 内容生成服务，支持多语言、个性化问候，并提供备用方案以确保服务稳定性。

## 目录结构

```
app/routers/event/
├── __init__.py
├── event_handler.py              # 主路由处理逻辑
├── schemas.py                    # 数据模型定义
├── content_generation_service.py # 内容生成服务
├── event_const.py                # 常量定义
├── utils.py                      # 工具函数
└── templates/                    # 模板目录
    ├── __init__.py
    ├── example_templates.py      # 示例模板
    └── fallback_templates.py     # 备用模板
```

## 主要功能

### 1. 问候语生成（Greet）

支持多种问候类型，使用 LLM 生成个性化问候语：

- **good_m**: 早安问候
- **good_n**: 晚安问候
- **good_l**: 深夜问候
- **good_w**: 周末问候
- **good_f**: 节日问候

### 2. 点评内容生成（Commentary）

根据用户输入的提示词生成点评内容，并自动发送消息到群组。

### 3. 多语言支持

支持多种语言的内容生成，包括：
- 中文（zh）
- 英文（en）
- 日文（ja）
- 其他语言

### 4. 备用方案

当 LLM 生成失败或内容过长时，自动降级使用预定义的备用模板。

## API 端点

### POST /api/initiative/event

处理不同类型的事件（greet 或 commentary）。

#### 请求参数

```json
{
  "event_type": "greet",
  "event_dict": {
    "greet_type": "good_m",
    "user_name": "张三",
    "language_code": "zh",
    "group_id": "group_123",
    "festival_name": "new_year"
  }
}
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| event_type | string | 是 | 事件类型：`greet` 或 `commentary` |
| event_dict | object | 是 | 事件参数字典 |

#### event_dict 参数（greet 事件）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| greet_type | string | 是 | 问候类型：`good_m`/`good_n`/`good_l`/`good_w`/`good_f` |
| user_name | string | 否 | 用户名，用于个性化问候 |
| language_code | string | 否 | 语言代码，默认根据上下文判断 |
| group_id | string | 是 | 群组 ID |
| festival_name | string | 条件必填 | 节日名称（仅 `good_f` 类型需要） |

#### event_dict 参数（commentary 事件）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message_id | string | 是 | 消息 ID |
| group_id | string | 是 | 群组 ID |
| prompt | string | 是 | 用户输入的提示词 |
| language_code | string | 否 | 语言代码 |
| user_name | string | 否 | 用户名 |

#### 响应示例

**成功响应（greet 事件）：**
```json
{
  "code": 200,
  "message": "问候语生成成功",
  "data": {
    "event_type": "greet",
    "greet_type": "good_m",
    "user_name": "张三",
    "greeting": "早安，张三！今天又是美好的一天！",
    "fallback": false
  }
}
```

**降级响应（LLM 失败）：**
```json
{
  "code": 503,
  "message": "LLM生成失败，已使用备用问候语",
  "data": {
    "event_type": "greet",
    "greet_type": "good_m",
    "user_name": "张三",
    "greeting": "早安！",
    "fallback": true,
    "error": "LLM生成失败: timeout"
  }
}
```

**成功响应（commentary 事件）：**
```json
{
  "code": 200,
  "message": "问候语生成成功",
  "data": {
    "event_type": "commentary",
    "greeting": "这个观点很有趣！",
    "fallback": false
  }
}
```

### GET /api/initiative/event

API 信息页，返回可用的端点列表。

#### 响应示例

```json
{
  "message": "Event Handler API",
  "endpoints": {
    "POST /api/initiative/event": "处理事件 greet 或 commentary",
    "GET /api/initiative/event": "Event Handler API 信息页"
  }
}
```

## 核心模块说明

### event_handler.py

主路由处理模块，负责：

1. 接收并验证事件请求
2. 根据事件类型分发处理逻辑
3. 调用内容生成服务
4. 处理评论事件的消息发送
5. 返回统一的响应格式

**主要函数：**
- `handle_event()`: 处理事件的主函数
- `root()`: API 信息页

### schemas.py

定义请求和响应的数据模型：

- `EventRequest`: 事件请求模型
- `ErrorResponse`: 错误响应模型
- `SuccessResponse`: 成功响应模型

### content_generation_service.py

内容生成服务模块，提供：

1. **ContentPromptManager**: Prompt 管理器
   - 加载和管理 prompt 配置文件
   - 构建个性化的 prompt
   - 支持多种问候类型和风格

2. **generate_content()**: 生成内容的主函数
   - 调用 LLM API 生成内容
   - 内容长度验证（CJK 语言按字符数，其他语言按单词数）
   - 失败时自动降级到备用方案

3. **get_fallback_content()**: 获取备用内容
   - 从预定义模板中随机选择
   - 支持多语言
   - 可选添加用户名（70% 概率）

**配置文件：**
- `greeting_prompts.json`: 问候语 prompt 配置
- `commentary_prompts.json`: 点评 prompt 配置

### event_const.py

定义常量：

```python
GREETING_TYPES = ["good_m", "good_n", "good_l", "good_w", "good_f"]

FESTIVALS = [
    "new_year", "valentines_day", "april_fools_day", "mothers_day",
    "fathers_day", "halloween_eve", "christmas_eve", "christmas"
]
```

### utils.py

工具函数模块：

1. **params_check_commentary()**: 验证 commentary 事件参数
2. **params_check_greet()**: 验证 greet 事件参数
3. **check_execution_probability_with_details()**: 检查执行概率

## 技术特点

### 1. 多语言支持

- 自动识别 CJK 语言（中文、日文、韩文）
- 根据上下文或指定语言代码生成内容
- 不同语言有不同的长度限制

### 2. 降级策略

- LLM 生成失败时使用备用模板
- 内容过长时自动降级
- 确保服务始终可用

### 3. 个性化生成

- 支持添加用户名
- 随机选择不同的风格
- 根据群组上下文生成内容

### 4. 错误处理

- 完善的参数验证
- 详细的错误信息
- 统一的响应格式

### 5. 日志记录

- 完整的请求日志
- 详细的错误日志
- 性能监控

## 环境变量配置

以下环境变量在 `.env` 文件中配置：

```env
# LLM 配置
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://app.onerouter.pro/v1
LLM_CHAT_CHECK_MODEL=gemini-3-flash-preview
LLM_TEMPERATURE=1.2
LLM_TIMEOUT=30.0

# 内容长度配置
MAX_GREETING_LENGTH_CJK=35
MAX_GREETING_LENGTH_EN=25

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_EXPIRE_TIME=180

# API 配置
SEND_REQ_URL=https://app.agnes-ai.com
```

## 使用示例

### 1. 发送早安问候

```bash
curl -X POST http://localhost:8800/api/initiative/event \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "greet",
    "event_dict": {
      "greet_type": "good_m",
      "user_name": "张三",
      "language_code": "zh",
      "group_id": "group_123"
    }
  }'
```

### 2. 发送节日问候

```bash
curl -X POST http://localhost:8800/api/initiative/event \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "greet",
    "event_dict": {
      "greet_type": "good_f",
      "festival_name": "new_year",
      "user_name": "李四",
      "language_code": "zh",
      "group_id": "group_456"
    }
  }'
```

### 3. 生成点评内容

```bash
curl -X POST http://localhost:8800/api/initiative/event \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "commentary",
    "event_dict": {
      "message_id": "msg_789",
      "group_id": "group_123",
      "prompt": "这个观点很有趣",
      "language_code": "zh",
      "user_name": "王五"
    }
  }'
```

## 错误处理

### 常见错误码

| 错误码 | 说明 |
|--------|------|
| 400 | 参数错误 |
| 500 | 内部服务器错误 |
| 503 | LLM 生成失败，已使用备用方案 |

### 错误响应示例

```json
{
  "code": 400,
  "message": "参数错误",
  "details": "greet 事件的 event_dict 需要包含 greet_type"
}
```

## 依赖服务

1. **LLM 服务**: OpenAI 兼容 API（如 OneRouter）
2. **Redis**: 存储群组上下文
3. **Agnes API**: 发送消息服务

## 注意事项

1. 确保 `.env` 文件中配置了正确的 API 密钥和 URL
2. Redis 服务需要正常运行以获取群组上下文
3. LLM 服务需要稳定的网络连接
4. 备用模板需要预先配置好
5. 建议监控 LLM 调用的成功率和响应时间

## 相关文档

- [API 交互文档](interact_api.md)
- [日志模块文档](log_module.md)