# 互动接口 (Interaction API) 文档

## 概述

互动接口用于处理群聊中的消息互动判断和点赞操作，支持两种互动类型：
- **message**: 对用户消息进行情感分析，根据情感类型决定是否点赞
- **others**: 对其他类型的互动（如图片、表情等）根据概率决定是否点赞

## 接口信息

- **模块路径**: `app/routers/interact/`
- **路由前缀**: `/api/initiative/interaction`
- **主要功能**: 消息情感识别、点赞触发、概率控制

## API 端点

### 1. POST /api/initiative/interaction

处理消息互动判断和点赞操作。

#### 请求参数

**Content-Type**: `application/json`

```json
{
  "msg_type": "message | others",
  "msg_dict": {
    "message_id": "string (必填)",
    "group_id": "string (必填)",
    "contents": "string (message 类型必填)",
    "is_agnes": "boolean (message 类型必填)"
  }
}
```

**字段说明**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| msg_type | string | 是 | 互动类型: "message" 或 "others" |
| msg_dict.message_id | string | 是 | 消息 ID |
| msg_dict.group_id | string | 是 | 群组 ID |
| msg_dict.contents | string | 条件必填 | 消息内容（msg_type="message" 时必填） |
| msg_dict.is_agnes | boolean | 条件必填 | 是否为系统消息（msg_type="message" 时必填） |

#### 响应格式

**成功响应** (HTTP 200):

```json
{
  "code": 200,
  "message": "string",
  "data": {
    "msg_type": "message | others",
    "action": "like | skipped | failed",
    "message_id": "string",
    "result": {}
  }
}
```

**错误响应** (HTTP 500):

```json
{
  "code": 500,
  "message": "点赞API调用失败",
  "details": "错误详情"
}
```

#### 请求示例

##### 示例 1: Message 类型 - 用户提及 @Agnes

```json
{
  "msg_type": "message",
  "msg_dict": {
    "message_id": "msg_12345",
    "group_id": "group_67890",
    "contents": "@Agnes 你好棒!",
    "is_agnes": false
  }
}
```

**响应**:
```json
{
  "code": 200,
  "message": "点赞成功",
  "data": {
    "msg_type": "message",
    "action": "like",
    "message_id": "msg_12345",
    "result": {
      "success": true,
      "data": {}
    }
  }
}
```

##### 示例 2: Message 类型 - 系统消息

```json
{
  "msg_type": "message",
  "msg_dict": {
    "message_id": "msg_11111",
    "group_id": "group_22222",
    "contents": "系统通知：群聊已更新",
    "is_agnes": true
  }
}
```

**响应**:
```json
{
  "code": 200,
  "message": "系统消息无需判断",
  "data": {
    "msg_type": "message",
    "message_id": "msg_11111",
    "action": "skipped",
    "is_agnes": true
  }
}
```

##### 示例 3: Message 类型 - 中性消息

```json
{
  "msg_type": "message",
  "msg_dict": {
    "message_id": "msg_33333",
    "group_id": "group_44444",
    "contents": "今天天气不错",
    "is_agnes": false
  }
}
```

**响应**:
```json
{
  "code": 200,
  "message": "中性消息，已跳过点赞",
  "data": {
    "msg_type": "message",
    "action": "skipped",
    "msg_emotions": 6
  }
}
```

##### 示例 4: Others 类型

```json
{
  "msg_type": "others",
  "msg_dict": {
    "message_id": "msg_55555",
    "group_id": "group_66666"
  }
}
```

**响应**:
```json
{
  "code": 200,
  "message": "点赞成功",
  "data": {
    "msg_type": "others",
    "action": "like",
    "message_id": "msg_55555",
    "result": {
      "success": true,
      "data": {}
    }
  }
}
```

### 2. GET /api/initiative/interaction

获取互动接口信息页。

#### 响应示例

```json
{
  "message": "Interact API",
  "endpoints": {
    "POST /api/initiative/interaction": "处理消息互动",
    "GET /api/initiative/interaction": "Interact接口信息页"
  }
}
```

## 业务逻辑

### Message 类型处理流程

```
┌─────────────────────┐
│  接收 message 请求   │
└──────────┬──────────┘
           │
           ▼
    ┌──────────────┐
    │ is_agnes?    │──Yes──▶ 跳过 (系统消息)
    └──────┬───────┘
           │ No
           ▼
    ┌──────────────┐
    │ LLM 情感分析  │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │ 情感类型判断  │
    └──────┬───────┘
           │
    ┌──────┴──────┬──────────┬────────┐
    │             │          │        │
    ▼             ▼          ▼        ▼
  0,2,3,4,5      6        其他      异常
  (有效情感)   (中性)    (非法)    (错误)
    │            │         │         │
    ▼            ▼         ▼         ▼
  概率判断     跳过      跳过      报错
    │
    ▼
┌────────────┐
│ 是否@Agnes? │
└─────┬──────┘
      │
  ┌───┴───┐
  │       │
  Yes     No (旁观者)
  │       │
  │       ▼
  │   ┌─────────────┐
  │   │ 80%概率判断  │
  │   └──────┬──────┘
  │          │
  │     ┌────┴─────┐
  │     │          │
  │    命中       未命中
  │     │          │
  └─────┤          ▼
        │         跳过
        ▼
   ┌─────────┐
   │ 调用点赞 │
   └─────────┘
```

### Others 类型处理流程

```
┌─────────────────────┐
│  接收 others 请求    │
└──────────┬──────────┘
           │
           ▼
    ┌──────────────┐
    │  概率判断     │
    │ (LIKE_PROB)  │
    └──────┬───────┘
           │
      ┌────┴─────┐
      │          │
     命中       未命中
      │          │
      ▼          ▼
   随机emoji    跳过
   (0-3)
      │
      ▼
   ┌─────────┐
   │ 调用点赞 │
   └─────────┘
```

## 情感标签说明

LLM 模型会将消息内容分析为以下 7 种情感类型：

| 标签值 | 情感类型 | 说明 | Emoji |
|--------|---------|------|-------|
| 0 | thumbs-up | 赞同/鼓励/积极 | 👍 |
| 2 | laugh | 搞笑/有趣 | 😂 |
| 3 | surprised | 惊讶/震惊 | 😮 |
| 4 | crying | 难过/抱歉 | 😢 |
| 5 | angry | 不满/生气 | 😠 |
| 6 | normal | 中性/不清楚/其他 | - |

**注意**: 标签值为 6 的消息会被跳过，不执行点赞操作。

## 配置参数

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| LIKE_PROBABILITY | 1.0 | others 类型点赞概率 (0-1) |
| LLM_CHAT_CHECK_MODEL | gemini-2.5-flash | 情感分析使用的 LLM 模型 |
| LLM_TIMEOUT | 15.0 | LLM 调用超时时间（秒） |
| OPENAI_API_KEY | - | OpenAI API Key（必填） |
| OPENAI_BASE_URL | https://app.onerouter.pro/v1 | OpenAI API 基础 URL |

### 常量配置

- **Message 旁观者概率**: 0.8 (80% 命中才点赞)
- **Message @Agnes**: 不启用随机性，必定点赞
- **Others 随机 emoji 范围**: 0-3

## 核心模块说明

### 1. schemas.py - 数据模型

定义请求和响应的 Pydantic 模型：

- **MessageDict**: 消息字典模型，包含 message_id、group_id、contents、is_agnes
- **InteractRequest**: 互动请求模型，包含 msg_type 和 msg_dict
- **field_validator**: 自动校验 message 类型必填字段

### 2. interact_handler.py - 路由处理

主要函数：

- **handle_msg_interact**: 处理互动请求的主函数
  - 参数校验
  - 消息类型路由
  - 情感分析调用
  - 概率判断
  - 点赞 API 调用

- **interact_root**: 返回接口信息页

### 3. interact_utils.py - 工具函数

主要函数：

- **analyze_message**: 调用 LLM 进行消息情感分析
  - 参数: message_content, is_bystander, client (可选), contexts (可选)
  - 返回: 0-6 的情感标签

- **_set_identity_role**: 根据是否为旁观者设置不同的角色提示词
  - 旁观者视角: 友好互动
  - 被提及视角: 强调降温、礼貌

- **_parse_label**: 解析 LLM 返回的情感标签
  - 容错处理: 非法值返回 6（中性）

## 日志记录

使用结构化日志记录所有关键操作：

```python
logger.info(
    "Interact接口请求开始",
    msg_type=msg_type,
    message_id=message_id,
    group_id=group_id
)
```

**关键日志点**:
- 请求开始/结束
- 系统消息跳过
- 情感识别完成
- 概率判断结果
- 点赞 API 调用成功/失败
- 异常错误

## 错误处理

### 1. 参数校验错误 (HTTP 422)

Pydantic 自动校验失败，返回详细的字段错误信息。

### 2. 模型异常 (HTTP 200, code: 500)

LLM 返回非法情感标签，返回：
```json
{
  "code": 500,
  "message": "模型异常，请检查模型输出",
  "data": {
    "msg_type": "message",
    "action": "failed",
    "msg_emotions": 99
  }
}
```

### 3. 点赞 API 调用失败 (HTTP 500)

外部点赞接口调用失败，抛出 HTTPException：
```json
{
  "code": 500,
  "message": "点赞API调用失败",
  "details": "网络错误"
}
```

### 4. LLM 调用异常

LLM 调用失败（网络超时、API 错误等），自动降级为中性情感（返回 6）。

## 测试

### 单元测试

测试文件位置：
- `tests/unit/test_interact_handler.py`: 路由处理函数测试
- `tests/unit/test_interact_utils.py`: 工具函数测试

运行测试：
```bash
# 运行所有互动模块测试
pytest tests/unit/test_interact_handler.py -v
pytest tests/unit/test_interact_utils.py -v

# 运行特定测试
pytest tests/unit/test_interact_handler.py::TestHandleMsgInteract::test_message_type_agnes_message_skipped -v
```

### 测试覆盖

- ✅ 系统消息跳过逻辑
- ✅ 中性消息跳过逻辑
- ✅ @Agnes 场景点赞逻辑
- ✅ 旁观者概率判断
- ✅ Others 类型点赞逻辑
- ✅ 所有情感类型识别 (0,2,3,4,5,6)
- ✅ 非法情感标签处理
- ✅ LLM 调用异常处理
- ✅ 点赞 API 调用失败处理
- ✅ 角色提示词切换
- ✅ 标签解析容错

## 最佳实践

### 1. 调用建议

- **高频消息**: 可调低 LIKE_PROBABILITY 避免点赞过于频繁
- **测试环境**: 建议设置 LIKE_PROBABILITY=1.0 方便调试
- **生产环境**: 建议 LIKE_PROBABILITY=0.3-0.5，避免过度互动

### 2. 性能优化

- LLM 调用设置了 15 秒超时，避免长时间阻塞
- 使用 `temperature=0.0` 确保情感分析结果稳定
- 异步 HTTP 调用，支持高并发

### 3. 监控要点

- LLM 调用成功率
- 点赞 API 调用成功率
- 非法情感标签出现频率
- 各情感类型分布比例

## 依赖服务

| 服务 | 用途 | 配置项 |
|------|------|--------|
| OpenAI API | 情感分析 | OPENAI_API_KEY, OPENAI_BASE_URL |
| 点赞 API | 执行点赞操作 | LIKE_API_URL |

## 常见问题

### Q1: 为什么中性消息不点赞？

**A**: 中性消息（如天气讨论、日常陈述）不包含明确的情感倾向，点赞可能显得不自然。系统将这类消息标记为标签 6 并跳过。

### Q2: 旁观者场景为什么要加概率控制？

**A**: 旁观者场景下，AI 不是对话参与者，如果对所有消息都点赞会显得过于主动。加入 80% 概率让互动更自然。

### Q3: @Agnes 场景为什么不用概率控制？

**A**: 用户明确 @AI 时，表示希望得到响应。此时点赞是一种积极的互动反馈，应该确定性触发。

### Q4: LLM 超时会影响点赞吗？

**A**: 不会。LLM 超时会被捕获并返回中性标签 6，消息会被跳过，不影响其他功能。

### Q5: 如何调试情感识别不准确？

**A**: 
1. 检查日志中的 `msg_emotions_flag` 字段
2. 调整 `prompts/message_analyze_prompts.json` 中的提示词
3. 尝试更换 LLM 模型（修改 LLM_CHAT_CHECK_MODEL）

## 更新日志

### v1.0.0 (2026-01-11)
- ✅ 实现 message 类型互动处理
- ✅ 实现 others 类型互动处理
- ✅ 支持 LLM 情感分析
- ✅ 实现概率控制逻辑
- ✅ 完善日志记录
- ✅ 添加单元测试覆盖

## 参考资料

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Pydantic 数据校验](https://docs.pydantic.dev/)
- [OpenAI API 文档](https://platform.openai.com/docs/api-reference)
