# server/tests/test_models.py
import pytest
from claude_notify.models import (
    NotifyRequest,
    NotifyResponse,
    ReplyResponse,
    SessionData,
    ActionType,
    StatusType,
)


def test_notify_request_valid():
    req = NotifyRequest(
        session_id="abc123",
        status=StatusType.COMPLETED,
        summary="Task completed",
        cwd="/home/user/project",
    )
    assert req.session_id == "abc123"
    assert req.status == StatusType.COMPLETED


def test_notify_request_with_buttons():
    req = NotifyRequest(
        session_id="abc123",
        status=StatusType.COMPLETED,
        summary="Task completed",
        cwd="/tmp",
        buttons=["继续", "结束"],
    )
    assert req.buttons == ["继续", "结束"]


def test_reply_response_no_reply():
    resp = ReplyResponse(has_reply=False)
    assert resp.has_reply is False
    assert resp.reply is None
    assert resp.action is None


def test_reply_response_with_reply():
    resp = ReplyResponse(
        has_reply=True,
        reply="请添加测试",
        action=ActionType.CONTINUE,
    )
    assert resp.has_reply is True
    assert resp.reply == "请添加测试"
    assert resp.action == ActionType.CONTINUE


def test_session_data_short_id():
    session = SessionData(
        session_id="abc123def456",
        chat_id=12345,
        cwd="/tmp",
    )
    assert session.short_id == "abc1"
