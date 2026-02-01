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
    assert "✅ 任务完成" in msg
    assert "#abc1" in msg
    assert "Task completed successfully" in msg
    assert "user/project" in msg  # 简化后只显示最后两级目录


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


def test_parse_action_cancel_no(bot):
    """Test 'no' is treated as cancel (for permission denial)."""
    action, reply = bot.parse_user_input("no")
    assert action == ActionType.CANCEL
    assert reply == "no"


def test_parse_action_cancel_reject(bot):
    """Test '拒绝' is treated as cancel."""
    action, reply = bot.parse_user_input("拒绝")
    assert action == ActionType.CANCEL
    assert reply == "拒绝"


def test_parse_action_continue(bot):
    action, reply = bot.parse_user_input("请添加测试")
    assert action == ActionType.CONTINUE
    assert reply == "请添加测试"


def test_parse_action_continue_yes(bot):
    """Test 'yes' is treated as continue (for permission approval)."""
    action, reply = bot.parse_user_input("yes")
    assert action == ActionType.CONTINUE
    assert reply == "yes"


def test_is_allowed_chat(bot):
    assert bot.is_allowed_chat(12345) is True
    assert bot.is_allowed_chat(99999) is False


# ============ New tests for session lookup and chat_id tracking ============


class TestSessionLookup:
    """Tests for session lookup in handle_message and handle_callback."""

    @pytest.fixture
    def mock_update(self):
        """Create a mock Update object."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "test reply"
        update.message.reply_text = AsyncMock()
        update.effective_chat = MagicMock()
        update.effective_chat.id = 12345
        update.message.reply_to_message = None
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock context."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_handle_message_finds_session_with_chat_id_zero(
        self, bot, store, mock_update, mock_context
    ):
        """Session created with chat_id=0 should be found via fallback."""
        # Create session with chat_id=0 (simulating API creating session)
        session = store.create_session(
            session_id="test-session-123",
            chat_id=0,  # Session created without knowing chat_id
            cwd="/test/project",
        )

        # User sends a message (not a reply)
        await bot.handle_message(mock_update, mock_context)

        # Should find the session and set reply
        assert session.pending_reply == "test reply"
        assert session.action == ActionType.CONTINUE
        # chat_id should be updated
        assert session.chat_id == 12345

    @pytest.mark.asyncio
    async def test_handle_message_finds_session_by_thread_id(
        self, bot, store, mock_update, mock_context
    ):
        """Session should be found by thread_id when user replies to message."""
        # Create session and set thread_id
        session = store.create_session(
            session_id="test-session-456",
            chat_id=12345,
            cwd="/test/project",
        )
        store.update_thread_id(
            session_id="test-session-456",
            message_id=999,
            thread_id=999,
            chat_id=12345,
        )

        # User replies to the notification message
        mock_update.message.reply_to_message = MagicMock()
        mock_update.message.reply_to_message.message_id = 999

        await bot.handle_message(mock_update, mock_context)

        # Should find session by thread_id
        assert session.pending_reply == "test reply"
        assert session.action == ActionType.CONTINUE

    @pytest.mark.asyncio
    async def test_handle_message_updates_chat_id_when_found_by_thread(
        self, bot, store, mock_update, mock_context
    ):
        """When session is found by thread_id, chat_id should be updated if it was 0."""
        # Create session with chat_id=0
        session = store.create_session(
            session_id="test-session-789",
            chat_id=0,
            cwd="/test/project",
        )
        store.update_thread_id(
            session_id="test-session-789",
            message_id=888,
            thread_id=888,
        )

        # User replies to the notification message
        mock_update.message.reply_to_message = MagicMock()
        mock_update.message.reply_to_message.message_id = 888

        await bot.handle_message(mock_update, mock_context)

        # chat_id should be updated from 0 to actual chat_id
        assert session.chat_id == 12345
        assert session.pending_reply == "test reply"

    @pytest.mark.asyncio
    async def test_handle_message_no_session_found(
        self, bot, store, mock_update, mock_context
    ):
        """Should show error when no session is found."""
        # No sessions in store
        await bot.handle_message(mock_update, mock_context)

        # Should reply with error message
        mock_update.message.reply_text.assert_called_with(
            "⚠️ 没有找到等待中的任务。"
        )

    @pytest.mark.asyncio
    async def test_handle_message_unauthorized_chat(
        self, bot, store, mock_update, mock_context
    ):
        """Should ignore messages from unauthorized chats."""
        mock_update.effective_chat.id = 99999  # Not in allowed list

        session = store.create_session(
            session_id="test-session",
            chat_id=0,
            cwd="/test",
        )

        await bot.handle_message(mock_update, mock_context)

        # Session should not be modified
        assert session.pending_reply is None


class TestCallbackHandler:
    """Tests for handle_callback function."""

    @pytest.fixture
    def mock_callback_update(self):
        """Create a mock Update with callback_query."""
        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.message = MagicMock()
        update.callback_query.message.chat_id = 12345
        update.callback_query.message.message_id = 777
        update.callback_query.message.text = "Original message"
        update.callback_query.message.reply_text = AsyncMock()
        update.callback_query.message.delete = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.data = "action:done"
        return update

    @pytest.fixture
    def mock_context(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_handle_callback_finds_session_by_message_id(
        self, bot, store, mock_callback_update, mock_context
    ):
        """Callback should find session by message_id (thread_id)."""
        session = store.create_session(
            session_id="callback-test-1",
            chat_id=12345,
            cwd="/test",
        )
        store.update_thread_id(
            session_id="callback-test-1",
            message_id=777,
            thread_id=777,
            chat_id=12345,
        )

        mock_callback_update.callback_query.data = "action:done"

        await bot.handle_callback(mock_callback_update, mock_context)

        assert session.pending_reply == "/done"
        assert session.action == ActionType.DONE

    @pytest.mark.asyncio
    async def test_handle_callback_fallback_to_waiting_session(
        self, bot, store, mock_callback_update, mock_context
    ):
        """Callback should fallback to any waiting session if thread lookup fails."""
        # Create session with chat_id=0 (no thread_id set)
        session = store.create_session(
            session_id="callback-test-2",
            chat_id=0,
            cwd="/test",
        )

        mock_callback_update.callback_query.data = "action:done"

        await bot.handle_callback(mock_callback_update, mock_context)

        # Should find session via fallback and update chat_id
        assert session.pending_reply == "/done"
        assert session.action == ActionType.DONE
        assert session.chat_id == 12345

    @pytest.mark.asyncio
    async def test_handle_callback_continue_action(
        self, bot, store, mock_callback_update, mock_context
    ):
        """Continue action should prompt for input."""
        session = store.create_session(
            session_id="callback-test-3",
            chat_id=12345,
            cwd="/test",
        )
        store.update_thread_id(
            session_id="callback-test-3",
            message_id=777,
            thread_id=777,
            chat_id=12345,
        )

        mock_callback_update.callback_query.data = "action:continue"

        await bot.handle_callback(mock_callback_update, mock_context)

        # Should prompt for input
        mock_callback_update.callback_query.message.reply_text.assert_called_with(
            "💬 请输入要继续执行的指令："
        )

    @pytest.mark.asyncio
    async def test_handle_callback_custom_button(
        self, bot, store, mock_callback_update, mock_context
    ):
        """Custom button should be treated as continue with button text."""
        session = store.create_session(
            session_id="callback-test-4",
            chat_id=12345,
            cwd="/test",
        )
        store.update_thread_id(
            session_id="callback-test-4",
            message_id=777,
            thread_id=777,
            chat_id=12345,
        )

        mock_callback_update.callback_query.data = "btn:Yes, proceed"

        await bot.handle_callback(mock_callback_update, mock_context)

        assert session.pending_reply == "Yes, proceed"
        assert session.action == ActionType.CONTINUE

    @pytest.mark.asyncio
    async def test_handle_callback_no_session_expired(
        self, bot, store, mock_callback_update, mock_context
    ):
        """Should show expired message when no session found."""
        # No sessions in store
        await bot.handle_callback(mock_callback_update, mock_context)

        mock_callback_update.callback_query.edit_message_text.assert_called_with(
            "Original message\n\n⚠️ Session 已过期"
        )

    @pytest.mark.asyncio
    async def test_handle_callback_unauthorized_chat(
        self, bot, store, mock_callback_update, mock_context
    ):
        """Should ignore callbacks from unauthorized chats."""
        mock_callback_update.callback_query.message.chat_id = 99999

        session = store.create_session(
            session_id="callback-test-5",
            chat_id=0,
            cwd="/test",
        )

        await bot.handle_callback(mock_callback_update, mock_context)

        # Session should not be modified
        assert session.pending_reply is None


class TestStoreListWaitingSessions:
    """Tests for list_waiting_sessions including chat_id=0 sessions."""

    def test_list_waiting_sessions_includes_chat_id_zero(self, store):
        """Sessions with chat_id=0 should be included in results."""
        # Create session with chat_id=0
        session1 = store.create_session(
            session_id="session-1",
            chat_id=0,
            cwd="/test1",
        )
        # Create session with matching chat_id
        session2 = store.create_session(
            session_id="session-2",
            chat_id=12345,
            cwd="/test2",
        )
        # Create session with different chat_id
        session3 = store.create_session(
            session_id="session-3",
            chat_id=99999,
            cwd="/test3",
        )

        waiting = store.list_waiting_sessions(12345)

        # Should include session1 (chat_id=0) and session2 (chat_id=12345)
        session_ids = [s.session_id for s in waiting]
        assert "session-1" in session_ids
        assert "session-2" in session_ids
        assert "session-3" not in session_ids

    def test_list_waiting_sessions_excludes_replied(self, store):
        """Sessions with pending_reply should be excluded."""
        session1 = store.create_session(
            session_id="session-1",
            chat_id=0,
            cwd="/test1",
        )
        session2 = store.create_session(
            session_id="session-2",
            chat_id=0,
            cwd="/test2",
        )
        # Set reply on session2
        store.set_reply("session-2", "test reply", ActionType.CONTINUE)

        waiting = store.list_waiting_sessions(12345)

        session_ids = [s.session_id for s in waiting]
        assert "session-1" in session_ids
        assert "session-2" not in session_ids

    def test_update_chat_id(self, store):
        """update_chat_id should update session's chat_id from 0."""
        session = store.create_session(
            session_id="session-1",
            chat_id=0,
            cwd="/test",
        )

        store.update_chat_id("session-1", 12345)

        assert session.chat_id == 12345

    def test_update_chat_id_only_updates_zero(self, store):
        """update_chat_id should only update if current chat_id is 0."""
        session = store.create_session(
            session_id="session-1",
            chat_id=11111,
            cwd="/test",
        )

        store.update_chat_id("session-1", 12345)

        # Should not change because original chat_id was not 0
        assert session.chat_id == 11111
