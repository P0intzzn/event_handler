"""
互动处理路由的单元测试

测试 interact_handler 模块的主要功能：
- message 类型互动处理
- others 类型互动处理
- 概率判断逻辑
- 错误处理
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException

from app.routers.interact.interact_handler import handle_msg_interact, interact_root
from app.routers.interact.schemas import InteractRequest, MessageDict


class TestHandleMsgInteract:
    """测试 handle_msg_interact 函数"""

    @pytest.mark.asyncio
    async def test_message_type_agnes_message_skipped(self):
        """测试系统消息被跳过"""
        request = InteractRequest(
            msg_type="message",
            msg_dict=MessageDict(
                message_id="msg_001",
                group_id="group_001",
                contents="系统消息",
                is_agnes=True
            )
        )

        result = await handle_msg_interact(request)

        assert result["code"] == 200
        assert result["message"] == "系统消息无需判断"
        assert result["data"]["action"] == "skipped"
        assert result["data"]["is_agnes"] is True

    @pytest.mark.asyncio
    async def test_message_type_neutral_emotion_skipped(self):
        """测试中性消息被跳过"""
        request = InteractRequest(
            msg_type="message",
            msg_dict=MessageDict(
                message_id="msg_002",
                group_id="group_002",
                contents="今天天气不错",
                is_agnes=False
            )
        )

        with patch("app.routers.interact.interact_handler.analyze_message", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = 6  # 中性消息

            result = await handle_msg_interact(request)

            assert result["code"] == 200
            assert result["message"] == "中性消息,已跳过点赞"
            assert result["data"]["action"] == "skipped"
            assert result["data"]["msg_emotions"] == 6

    @pytest.mark.asyncio
    async def test_message_type_positive_emotion_with_mention(self):
        """测试 @Agnes 场景积极消息触发点赞"""
        request = InteractRequest(
            msg_type="message",
            msg_dict=MessageDict(
                message_id="msg_003",
                group_id="group_003",
                contents="@Agnes 你好棒!",
                is_agnes=False
            )
        )

        with patch("app.routers.interact.interact_handler.analyze_message", new_callable=AsyncMock) as mock_analyze, \
            patch("app.routers.interact.interact_handler.call_like_api", new_callable=AsyncMock) as mock_like:
            mock_analyze.return_value = 0  # 积极情感
            mock_like.return_value = {"success": True, "data": {"status": "ok"}}

            result = await handle_msg_interact(request)

            assert result["code"] == 200
            assert result["message"] == "点赞成功"
            assert result["data"]["action"] == "like"
            mock_analyze.assert_called_once_with("@Agnes 你好棒!", False)
            mock_like.assert_called_once_with("msg_003", "group_003", "0")

    @pytest.mark.asyncio
    async def test_message_type_bystander_probability_not_hit(self):
        """测试旁观者场景概率未命中"""
        request = InteractRequest(
            msg_type="message",
            msg_dict=MessageDict(
                message_id="msg_004",
                group_id="group_004",
                contents="真不错",
                is_agnes=False
            )
        )

        with patch("app.routers.interact.interact_handler.analyze_message", new_callable=AsyncMock) as mock_analyze, \
            patch("app.routers.interact.interact_handler.check_probability_threshold") as mock_prob:
            mock_analyze.return_value = 0
            mock_prob.return_value = (False, 0.85)  # 未命中

            result = await handle_msg_interact(request)

            assert result["code"] == 200
            assert result["message"] == "未命中执行概率,已跳过点赞"
            assert result["data"]["action"] == "skipped"
            assert result["data"]["probability_threshold"] == 0.8
            assert result["data"]["random_value"] == 0.85

    @pytest.mark.asyncio
    async def test_message_type_invalid_emotion_label(self):
        """测试模型返回非法情感标签"""
        request = InteractRequest(
            msg_type="message",
            msg_dict=MessageDict(
                message_id="msg_005",
                group_id="group_005",
                contents="测试消息",
                is_agnes=False
            )
        )

        with patch("app.routers.interact.interact_handler.analyze_message", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = 99  # 非法值

            result = await handle_msg_interact(request)

            assert result["code"] == 500
            assert result["message"] == "模型异常,请检查模型输出"
            assert result["data"]["action"] == "failed"
            assert result["data"]["msg_emotions"] == 99

    @pytest.mark.asyncio
    async def test_others_type_probability_not_hit(self):
        """测试 others 类型概率未命中"""
        request = InteractRequest(
            msg_type="others",
            msg_dict=MessageDict(
                message_id="msg_006",
                group_id="group_006"
            )
        )

        with patch("app.routers.interact.interact_handler.check_probability_threshold") as mock_prob:
            mock_prob.return_value = (False, 0.95)

            result = await handle_msg_interact(request)

            assert result["code"] == 200
            assert result["message"] == "未命中执行概率,已跳过点赞"
            assert result["data"]["action"] == "skipped"

    @pytest.mark.asyncio
    async def test_others_type_probability_hit_success(self):
        """测试 others 类型概率命中且点赞成功"""
        request = InteractRequest(
            msg_type="others",
            msg_dict=MessageDict(
                message_id="msg_007",
                group_id="group_007"
            )
        )

        with patch("app.routers.interact.interact_handler.check_probability_threshold") as mock_prob, \
            patch("app.routers.interact.interact_handler.call_like_api", new_callable=AsyncMock) as mock_like, \
            patch("app.routers.interact.interact_handler.random.randint") as mock_randint:
            mock_prob.return_value = (True, 0.3)
            mock_randint.return_value = 2
            mock_like.return_value = {"success": True, "data": {"status": "ok"}}

            result = await handle_msg_interact(request)

            assert result["code"] == 200
            assert result["message"] == "点赞成功"
            assert result["data"]["action"] == "like"
            mock_like.assert_called_once_with("msg_007", "group_007", "2")

    @pytest.mark.asyncio
    async def test_like_api_call_failure(self):
        """测试点赞 API 调用失败"""
        request = InteractRequest(
            msg_type="others",
            msg_dict=MessageDict(
                message_id="msg_008",
                group_id="group_008"
            )
        )

        with patch("app.routers.interact.interact_handler.check_probability_threshold") as mock_prob, \
            patch("app.routers.interact.interact_handler.call_like_api", new_callable=AsyncMock) as mock_like:
            mock_prob.return_value = (True, 0.3)
            mock_like.return_value = {"success": False, "error": "网络错误"}

            with pytest.raises(HTTPException) as exc_info:
                await handle_msg_interact(request)

            assert exc_info.value.status_code == 500
            assert exc_info.value.detail["code"] == 500
            assert exc_info.value.detail["message"] == "点赞API调用失败"

    @pytest.mark.asyncio
    async def test_message_type_all_emotion_types(self):
        """测试所有合法的情感类型(0,2,3,4,5)"""
        valid_emotions = [0, 2, 3, 4, 5]

        for emotion in valid_emotions:
            request = InteractRequest(
                msg_type="message",
                msg_dict=MessageDict(
                    message_id=f"msg_{emotion}",
                    group_id="group_test",
                    contents="@Agnes 测试",
                    is_agnes=False
                )
            )

            with patch("app.routers.interact.interact_handler.analyze_message", new_callable=AsyncMock) as mock_analyze, \
                 patch("app.routers.interact.interact_handler.call_like_api", new_callable=AsyncMock) as mock_like:
                mock_analyze.return_value = emotion
                mock_like.return_value = {"success": True, "data": {}}

                result = await handle_msg_interact(request)

                assert result["code"] == 200
                assert result["message"] == "点赞成功"
                mock_like.assert_called_once_with(f"msg_{emotion}", "group_test", str(emotion))


class TestInteractRoot:
    """测试 interact_root 函数"""

    def test_interact_root_returns_info(self):
        """测试接口信息页返回正确的信息"""
        result = interact_root()

        assert result["message"] == "Interact API"
        assert "endpoints" in result
        assert "POST /api/initiative/interaction" in result["endpoints"]
        assert "GET /api/initiative/interaction" in result["endpoints"]
