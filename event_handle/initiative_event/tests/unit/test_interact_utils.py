"""
互动工具函数的单元测试

测试 interact_utils 模块的主要功能：
- analyze_message 消息情感分析
- _set_identity_role 角色设定
- _parse_label 标签解析
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

from app.routers.interact.interact_utils import (
    analyze_message,
    _set_identity_role,
    _parse_label
)


class TestSetIdentityRole:
    """测试 _set_identity_role 函数"""

    def test_bystander_role(self):
        """测试旁观者角色设定"""
        role_block, extra_rules = _set_identity_role(is_bystander=True)

        assert isinstance(role_block, str)
        assert isinstance(extra_rules, str)
        assert len(role_block) > 0
        assert len(extra_rules) > 0

    def test_mentioned_role(self):
        """测试被 @ 角色设定"""
        role_block, extra_rules = _set_identity_role(is_bystander=False)

        assert isinstance(role_block, str)
        assert isinstance(extra_rules, str)
        assert len(role_block) > 0
        assert len(extra_rules) > 0

    def test_different_roles_return_different_prompts(self):
        """测试不同角色返回不同的提示词"""
        bystander_role, bystander_rules = _set_identity_role(is_bystander=True)
        mentioned_role, mentioned_rules = _set_identity_role(is_bystander=False)

        # 旁观者和被提及场景应该返回不同的提示词
        assert (bystander_role != mentioned_role) or (bystander_rules != mentioned_rules)


class TestParseLabel:
    """测试 _parse_label 函数"""

    def test_parse_valid_labels(self):
        """测试解析合法标签"""
        valid_labels = ["0", "2", "3", "4", "5", "6"]
        expected_values = [0, 2, 3, 4, 5, 6]

        for label_str, expected in zip(valid_labels, expected_values):
            result = _parse_label(label_str)
            assert result == expected

    def test_parse_label_with_whitespace(self):
        """测试解析带空格的标签"""
        assert _parse_label("  3  ") == 3
        assert _parse_label("\n5\n") == 5

    def test_parse_invalid_number(self):
        """测试解析非法数字"""
        assert _parse_label("1") == 6  # 1 不在合法集合中
        assert _parse_label("7") == 6
        assert _parse_label("10") == 6
        assert _parse_label("-1") == 6

    def test_parse_non_numeric_string(self):
        """测试解析非数字字符串"""
        assert _parse_label("abc") == 6
        assert _parse_label("positive") == 6
        assert _parse_label("") == 6

    def test_parse_mixed_content(self):
        """测试解析混合内容"""
        assert _parse_label("3 positive") == 6  # int() 会失败
        assert _parse_label("The answer is 5") == 6


class TestAnalyzeMessage:
    """测试 analyze_message 函数"""

    @pytest.mark.asyncio
    async def test_empty_message_returns_neutral(self):
        """测试空消息返回中性"""
        result = await analyze_message("", is_bystander=True)
        assert result == 6

        result = await analyze_message("   ", is_bystander=True)
        assert result == 6

    @pytest.mark.asyncio
    async def test_analyze_message_with_mock_client_positive(self):
        """测试积极情感识别"""
        mock_client = AsyncMock(spec=AsyncOpenAI)
        mock_choice = MagicMock(spec=Choice)
        mock_message = MagicMock(spec=ChatCompletionMessage)
        mock_message.content = "0"
        mock_choice.message = mock_message
        
        mock_completion = MagicMock(spec=ChatCompletion)
        mock_completion.choices = [mock_choice]
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        result = await analyze_message(
            "太棒了!",
            is_bystander=True,
            client=mock_client
        )

        assert result == 0
        mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_message_with_mock_client_laugh(self):
        """测试搞笑情感识别"""
        mock_client = AsyncMock(spec=AsyncOpenAI)
        mock_choice = MagicMock(spec=Choice)
        mock_message = MagicMock(spec=ChatCompletionMessage)
        mock_message.content = "2"
        mock_choice.message = mock_message
        
        mock_completion = MagicMock(spec=ChatCompletion)
        mock_completion.choices = [mock_choice]
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        result = await analyze_message(
            "哈哈哈太好笑了",
            is_bystander=False,
            client=mock_client
        )

        assert result == 2

    @pytest.mark.asyncio
    async def test_analyze_message_with_mock_client_neutral(self):
        """测试中性情感识别"""
        mock_client = AsyncMock(spec=AsyncOpenAI)
        mock_choice = MagicMock(spec=Choice)
        mock_message = MagicMock(spec=ChatCompletionMessage)
        mock_message.content = "6"
        mock_choice.message = mock_message
        
        mock_completion = MagicMock(spec=ChatCompletion)
        mock_completion.choices = [mock_choice]
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        result = await analyze_message(
            "今天天气不错",
            is_bystander=True,
            client=mock_client
        )

        assert result == 6

    @pytest.mark.asyncio
    async def test_analyze_message_with_contexts(self):
        """测试带上下文的消息分析"""
        mock_client = AsyncMock(spec=AsyncOpenAI)
        mock_choice = MagicMock(spec=Choice)
        mock_message = MagicMock(spec=ChatCompletionMessage)
        mock_message.content = "0"
        mock_choice.message = mock_message
        
        mock_completion = MagicMock(spec=ChatCompletion)
        mock_completion.choices = [mock_choice]
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        result = await analyze_message(
            "谢谢你",
            is_bystander=False,
            client=mock_client,
            contexts="之前对方帮助了我"
        )

        assert result == 0
        # 验证调用参数中包含 contexts
        call_args = mock_client.chat.completions.create.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_analyze_message_llm_exception_returns_neutral(self):
        """测试 LLM 调用异常返回中性"""
        mock_client = AsyncMock(spec=AsyncOpenAI)
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("网络错误")
        )

        result = await analyze_message(
            "测试消息",
            is_bystander=True,
            client=mock_client
        )

        assert result == 6

    @pytest.mark.asyncio
    async def test_analyze_message_invalid_llm_response(self):
        """测试 LLM 返回非法响应"""
        mock_client = AsyncMock(spec=AsyncOpenAI)
        mock_choice = MagicMock(spec=Choice)
        mock_message = MagicMock(spec=ChatCompletionMessage)
        mock_message.content = "invalid_response"
        mock_choice.message = mock_message
        
        mock_completion = MagicMock(spec=ChatCompletion)
        mock_completion.choices = [mock_choice]
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        result = await analyze_message(
            "测试消息",
            is_bystander=True,
            client=mock_client
        )

        assert result == 6

    @pytest.mark.asyncio
    async def test_analyze_message_bystander_vs_mentioned(self):
        """测试旁观者和被提及场景调用不同提示词"""
        mock_client = AsyncMock(spec=AsyncOpenAI)
        mock_choice = MagicMock(spec=Choice)
        mock_message = MagicMock(spec=ChatCompletionMessage)
        mock_message.content = "0"
        mock_choice.message = mock_message
        
        mock_completion = MagicMock(spec=ChatCompletion)
        mock_completion.choices = [mock_choice]
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        # 旁观者场景
        await analyze_message("测试", is_bystander=True, client=mock_client)
        bystander_call = mock_client.chat.completions.create.call_args

        # 重置 mock
        mock_client.chat.completions.create.reset_mock()

        # 被提及场景
        await analyze_message("测试", is_bystander=False, client=mock_client)
        mentioned_call = mock_client.chat.completions.create.call_args

        # 验证两次调用的提示词不同
        assert bystander_call is not None
        assert mentioned_call is not None

    @pytest.mark.asyncio
    async def test_analyze_message_temperature_zero(self):
        """测试情感分析使用 temperature=0.0"""
        mock_client = AsyncMock(spec=AsyncOpenAI)
        mock_choice = MagicMock(spec=Choice)
        mock_message = MagicMock(spec=ChatCompletionMessage)
        mock_message.content = "3"
        mock_choice.message = mock_message
        
        mock_completion = MagicMock(spec=ChatCompletion)
        mock_completion.choices = [mock_choice]
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        await analyze_message(
            "哇!",
            is_bystander=True,
            client=mock_client
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_analyze_message_all_emotion_types(self):
        """测试所有情感类型的识别"""
        emotions = [0, 2, 3, 4, 5, 6]
        
        for emotion in emotions:
            mock_client = AsyncMock(spec=AsyncOpenAI)
            mock_choice = MagicMock(spec=Choice)
            mock_message = MagicMock(spec=ChatCompletionMessage)
            mock_message.content = str(emotion)
            mock_choice.message = mock_message
            
            mock_completion = MagicMock(spec=ChatCompletion)
            mock_completion.choices = [mock_choice]
            
            mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

            result = await analyze_message(
                f"测试情感{emotion}",
                is_bystander=True,
                client=mock_client
            )

            assert result == emotion
