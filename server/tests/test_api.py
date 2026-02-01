# server/tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from claude_notify.api import create_app
from claude_notify.store import SessionStore
from claude_notify.models import ActionType


@pytest.fixture
def store():
    return SessionStore()


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.send_notification = AsyncMock(return_value=(100, 200))
    bot.send_ack = AsyncMock()
    return bot


@pytest.fixture
def client(store, mock_bot, mock_settings):
    app = create_app(store=store, bot=mock_bot, api_key="test_api_key")
    return TestClient(app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_notify_success(client, store, mock_bot):
    response = client.post(
        "/notify",
        json={
            "session_id": "abc123",
            "status": "completed",
            "summary": "Task done",
            "cwd": "/tmp",
        },
        headers={"Authorization": "Bearer test_api_key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["message_id"] == 100
    assert data["thread_id"] == 200


def test_notify_unauthorized(client):
    response = client.post(
        "/notify",
        json={
            "session_id": "abc123",
            "status": "completed",
            "summary": "Task done",
            "cwd": "/tmp",
        },
        headers={"Authorization": "Bearer wrong_key"},
    )
    assert response.status_code == 401


def test_notify_no_auth(client):
    response = client.post(
        "/notify",
        json={
            "session_id": "abc123",
            "status": "completed",
            "summary": "Task done",
            "cwd": "/tmp",
        },
    )
    assert response.status_code == 401


def test_reply_no_reply(client, store, mock_settings):
    store.create_session("abc123", 12345, "/tmp")
    response = client.get(
        "/reply/abc123",
        headers={"Authorization": "Bearer test_api_key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_reply"] is False


def test_reply_with_reply(client, store, mock_settings):
    store.create_session("abc123", 12345, "/tmp")
    store.set_reply("abc123", "请继续", ActionType.CONTINUE)
    response = client.get(
        "/reply/abc123",
        headers={"Authorization": "Bearer test_api_key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_reply"] is True
    assert data["reply"] == "请继续"
    assert data["action"] == "continue"


def test_reply_not_found(client, mock_settings):
    response = client.get(
        "/reply/nonexistent",
        headers={"Authorization": "Bearer test_api_key"},
    )
    assert response.status_code == 404


def test_ack_success(client, store, mock_bot, mock_settings):
    store.create_session("abc123", 12345, "/tmp")
    store.set_reply("abc123", "请继续", ActionType.CONTINUE)
    response = client.post(
        "/ack/abc123",
        headers={"Authorization": "Bearer test_api_key"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    # Verify reply was cleared
    session = store.get_session("abc123")
    assert session.pending_reply is None


def test_ack_not_found(client, mock_settings):
    response = client.post(
        "/ack/nonexistent",
        headers={"Authorization": "Bearer test_api_key"},
    )
    assert response.status_code == 404
