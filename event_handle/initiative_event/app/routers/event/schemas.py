"""
事件处理路由的 Pydantic 数据模型

定义请求和响应的数据结构，用于事件处理相关的 API 接口
"""
from typing import Optional, Literal, Dict, Any, List
from pydantic import BaseModel, Field, field_validator

class EventDict(BaseModel):
    """事件参数字典模型
    
    根据事件类型不同，需要提供不同的必传字段：
    - greet 事件：需要提供 greet_type
    - commentary 事件：需要提供 message_id
    """
    group_id: str = Field(..., description="群组ID")
    message_id: Optional[str] = Field(None, description="消息ID，commentary事件必传")
    user_name: Optional[str] = Field(None, description="用户名称")
    greet_type: Optional[str] = Field(None, description="问候类型，greet事件必传")
    festival_name: Optional[str] = Field(None, description="节日名称")
    is_template: Optional[bool] = Field(False, description="是否为模板")
    prompt: Optional[str] = Field(None, description="生成物的提示词")
    user_upload_url: Optional[List[str]] = Field(None, description="用户素材的URL列表")
    s3_url: Optional[str] = Field(None, description="模板生成物的URL")
    language_code: Optional[str] = Field("en", description="语言代码，默认en")
    topic: Optional[str] = Field(None, description="群聊主题")
    push_type: Optional[Literal["video", "news", "websearch", "text"]] = Field(None, description="推送类型")
    push_value: Optional[str] = Field(None, description="推送内容")


class EventRequest(BaseModel):
    """
    事件请求模型
    
    支持的事件类型：
    - greet: 问候语生成事件
    - commentary: 点评事件
    """
    event_type: Literal["greet", "commentary"] = Field(..., description="事件类型：greet（问候）、commentary（点评）")
    event_dict: EventDict = Field(..., description="事件参数字典，根据 event_type 不同包含不同字段")
    
    @field_validator('event_dict')
    @classmethod
    def validate_event_dict(cls, v: EventDict, info) -> EventDict:
        """验证事件参数字典，确保必传字段完整"""
        event_type = info.data.get('event_type')
        if not event_type:
            return v
        
        # 根据事件类型验证特定必传参数
        if event_type == 'greet':
            if not v.greet_type:
                raise ValueError('greet事件缺少必传参数: greet_type')         
        elif event_type == 'commentary':
            if not v.message_id:
                raise ValueError('commentary事件缺少必传参数: message_id')

        return v
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "event_type": "commentary",
                    "event_dict": {
                        "message_id": "msg_123",
                        "group_id": "group_456",
                        "prompt": "这个观点很有趣",
                        "language_code": "zh",
                        "user_name": "张三",
                        "user_upload_url": ["https://example.com/image1.jpg", "https://example.com/video1.mp4"],
                        "topic": "技术讨论"
                    }
                },
                {
                    "event_type": "greet",
                    "event_dict": {
                        "greet_type": "good_m",
                        "user_name": "张三",
                        "language_code": "zh",
                        "group_id": "group_123",
                        "festival_name": "new_year",
                        "is_template": True,
                        "push_type": "news"
                    }
                }
            ]
        }


class ErrorResponse(BaseModel):
    """错误响应模型"""
    code: int = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: Optional[str] = Field(None, description="错误详情")
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": 400,
                "message": "参数错误",
                "details": "event_type 必须是 'greet' 或 'commentary'"
            }
        }


class SuccessResponse(BaseModel):
    """成功响应模型"""
    code: int = Field(200, description="响应代码")
    message: str = Field(..., description="响应消息")
    data: Dict[str, Any] = Field(..., description="响应数据")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "code": 200,
                    "message": "操作成功",
                    "data": {
                        "event_type": "greet",
                        "greet_type": "good_m",
                        "user_name": "张三",
                        "greeting": "早上好！",
                        "fallback": False,
                        "focal_figure": "Kobe",
                        "topic_hot": "NBA",
                        "topic_ext": "足球",
                        "language_code": "zh"
                    }
                },
                {
                    "code": 200,
                    "message": "操作成功",
                    "data": {
                        "event_type": "commentary",
                        "message_id": "msg_123",
                        "commentary": "这个观点很有见地，值得深入讨论",
                        "language_code": "zh",
                        "user_name": "张三"
                    }
                }
            ]
        }
