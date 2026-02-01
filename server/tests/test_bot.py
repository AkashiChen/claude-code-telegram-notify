# server/tests/test_bot.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from claude_notify.bot import TelegramNotifyBot
from claude_notify.store import SessionStore
from claude_notify.models import ActionType, StatusType


@pytest.fixture
def store():
    return SessionStore()


@pytest.fixture
def bot(store):
    return TelegramNotifyBot(
        token="test_token",
        allowed_chat_ids=[12345],
        store=store,
    )


def test_bot_init(bot):
    assert bot.allowed_chat_ids == [12345]


def test_format_message_completed(bot):
    msg = bot.format_message(
        session_id="abc123def456",
        status=StatusType.COMPLETED,
        summary="Task completed successfully",
        cwd="/home/user/project",
    )
    assert "🤖 Claude Code #abc1" in msg
    assert "✅ 任务完成" in msg
    assert "Task completed successfully" in msg
    assert "/home/user/project" in msg


def test_format_message_permission(bot):
    msg = bot.format_message(
        session_id="abc123",
        status=StatusType.PERMISSION,
        summary="Need permission",
        cwd="/tmp",
    )
    assert "🔐 需要权限" in msg


def test_format_message_idle(bot):
    msg = bot.format_message(
        session_id="abc123",
        status=StatusType.IDLE,
        summary="Waiting",
        cwd="/tmp",
    )
    assert "⏳ 等待输入" in msg


def test_parse_action_done(bot):
    action, reply = bot.parse_user_input("/done")
    assert action == ActionType.DONE
    assert reply == "/done"


def test_parse_action_cancel(bot):
    action, reply = bot.parse_user_input("/cancel")
    assert action == ActionType.CANCEL
    assert reply == "/cancel"


def test_parse_action_continue(bot):
    action, reply = bot.parse_user_input("请添加测试")
    assert action == ActionType.CONTINUE
    assert reply == "请添加测试"


def test_is_allowed_chat(bot):
    assert bot.is_allowed_chat(12345) is True
    assert bot.is_allowed_chat(99999) is False
