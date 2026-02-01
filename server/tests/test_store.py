# server/tests/test_store.py
import pytest
from datetime import datetime, timedelta
from claude_notify.store import SessionStore
from claude_notify.models import SessionData, ActionType


@pytest.fixture
def store():
    return SessionStore()


def test_create_session(store):
    session = store.create_session(
        session_id="abc123",
        chat_id=12345,
        cwd="/tmp/project",
    )
    assert session.session_id == "abc123"
    assert session.chat_id == 12345


def test_get_session(store):
    store.create_session("abc123", 12345, "/tmp")
    session = store.get_session("abc123")
    assert session is not None
    assert session.session_id == "abc123"


def test_get_session_not_found(store):
    session = store.get_session("nonexistent")
    assert session is None


def test_update_thread_id(store):
    store.create_session("abc123", 12345, "/tmp")
    store.update_thread_id("abc123", message_id=100, thread_id=200)
    session = store.get_session("abc123")
    assert session.message_id == 100
    assert session.thread_id == 200


def test_set_reply(store):
    store.create_session("abc123", 12345, "/tmp")
    store.set_reply("abc123", "请继续", ActionType.CONTINUE)
    session = store.get_session("abc123")
    assert session.pending_reply == "请继续"
    assert session.action == ActionType.CONTINUE


def test_clear_reply(store):
    store.create_session("abc123", 12345, "/tmp")
    store.set_reply("abc123", "请继续", ActionType.CONTINUE)
    store.clear_reply("abc123")
    session = store.get_session("abc123")
    assert session.pending_reply is None
    assert session.action is None


def test_get_session_by_thread(store):
    store.create_session("abc123", 12345, "/tmp")
    store.update_thread_id("abc123", message_id=100, thread_id=200)
    session = store.get_session_by_thread(200)
    assert session is not None
    assert session.session_id == "abc123"


def test_get_session_by_thread_not_found(store):
    session = store.get_session_by_thread(999)
    assert session is None


def test_cleanup_expired(store):
    # Create an expired session
    store.create_session("old123", 12345, "/tmp")
    store._sessions["old123"].created_at = datetime.now() - timedelta(hours=25)

    # Create a fresh session
    store.create_session("new456", 12345, "/tmp")

    # Cleanup with 24 hour expiry
    store.cleanup_expired(86400)

    assert store.get_session("old123") is None
    assert store.get_session("new456") is not None


def test_list_waiting_sessions(store):
    store.create_session("abc123", 12345, "/tmp")
    store.create_session("def456", 12345, "/tmp")
    store.set_reply("def456", "done", ActionType.DONE)

    waiting = store.list_waiting_sessions(12345)
    assert len(waiting) == 1
    assert waiting[0].session_id == "abc123"
