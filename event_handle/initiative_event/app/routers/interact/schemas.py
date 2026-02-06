"""
互动处理路由的 Pydantic 数据模型

定义请求和响应的数据结构
"""


from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class MessageDict(BaseModel):
    """消息字典数据模型"""
    message_id: str = Field(..., description="消息ID")
    group_id: str = Field(..., description="群组ID")
    contents: Optional[str] = Field(None, description="消息内容（message类型必填）")
    is_agnes: bool = Field(..., description="是否为系统消息")


class InteractRequest(BaseModel):
    """互动请求数据模型"""
    msg_type: Literal["message", "others"] = Field(..., description="消息类型")
    msg_dict: MessageDict = Field(..., description="消息详情")
    
    @field_validator('msg_dict')
    @classmethod
    def validate_message_type_fields(cls, v: MessageDict, info) -> MessageDict:
        """针对 message 类型验证必填字段"""
        msg_type = info.data.get('msg_type')
        if msg_type == 'message':
            if v.contents is None:
                raise ValueError('msg_type为message时，contents字段必填')
        return v
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "summary": "用户文本消息示例",
                    "description": "msg_type 为 message 时，contents 字段必填，is_agnes 为 False",
                    "value": {
                        "msg_type": "message",
                        "msg_dict": {
                            "message_id": "msg_123",
                            "group_id": "group_456",
                            "contents": "今天天气真不错！",
                            "is_agnes": False
                        }
                    }
                },
                {
                    "summary": "其他类型消息示例",
                    "description": "msg_type 为 others 时，contents 字段可选（本示例中省略）",
                    "value": {
                        "msg_type": "others",
                        "msg_dict": {
                            "message_id": "msg_789",
                            "group_id": "group_456",
                            "is_agnes": False
                        }
                    }
                }
            ]
        }