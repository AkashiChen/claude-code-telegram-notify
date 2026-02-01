"""Telegram Bot for Claude Code notifications."""

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from .models import ActionType, StatusType
from .store import SessionStore

logger = logging.getLogger(__name__)


class TelegramNotifyBot:
    """Telegram bot for handling Claude Code notifications."""

    STATUS_EMOJI = {
        StatusType.COMPLETED: "✅ 任务完成",
        StatusType.PERMISSION: "🔐 需要权限",
        StatusType.IDLE: "⏳ 等待输入",
    }

    def __init__(
        self,
        token: str,
        allowed_chat_ids: List[int],
        store: SessionStore,
    ):
        self.token = token
        self.allowed_chat_ids = allowed_chat_ids
        self.store = store
        self.app: Optional[Application] = None

    def is_allowed_chat(self, chat_id: int) -> bool:
        """Check if chat is in allowed list."""
        return chat_id in self.allowed_chat_ids

    def format_message(
        self,
        session_id: str,
        status: StatusType,
        summary: str,
        cwd: str,
    ) -> str:
        """Format notification message."""
        short_id = session_id[:4]
        status_text = self.STATUS_EMOJI.get(status, "📋 通知")

        # 简化目录显示：只显示最后两级
        cwd_parts = cwd.rstrip('/').split('/')
        short_cwd = '/'.join(cwd_parts[-2:]) if len(cwd_parts) > 2 else cwd

        return f"""{status_text} #{short_id}
📁 {short_cwd}

{summary}"""

    def get_keyboard(
        self,
        buttons: Optional[List[str]] = None,
    ) -> InlineKeyboardMarkup:
        """Create inline keyboard."""
        if buttons:
            # 所有按钮放在一行
            keyboard = [[
                InlineKeyboardButton(btn, callback_data=f"btn:{btn}")
                for btn in buttons
            ]]
        else:
            keyboard = [[
                InlineKeyboardButton("继续", callback_data="action:continue"),
                InlineKeyboardButton("结束", callback_data="action:done"),
            ]]
        return InlineKeyboardMarkup(keyboard)

    def parse_user_input(self, text: str) -> Tuple[ActionType, str]:
        """Parse user input to determine action."""
        text = text.strip()
        if text.lower() in ["/done", "done", "结束"]:
            return ActionType.DONE, text
        elif text.lower() in ["/cancel", "cancel", "取消", "no", "拒绝"]:
            return ActionType.CANCEL, text
        else:
            return ActionType.CONTINUE, text

    async def send_notification(
        self,
        session_id: str,
        status: StatusType,
        summary: str,
        cwd: str,
        buttons: Optional[List[str]] = None,
        existing_thread_id: Optional[int] = None,
    ) -> Tuple[int, int, int]:
        """Send notification to Telegram. Returns (message_id, thread_id, chat_id)."""
        if not self.app:
            raise RuntimeError("Bot not initialized")

        chat_id = self.allowed_chat_ids[0]  # Primary chat
        message_text = self.format_message(session_id, status, summary, cwd)
        keyboard = self.get_keyboard(buttons)

        if existing_thread_id:
            # Reply in existing thread
            msg = await self.app.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=keyboard,
                reply_to_message_id=existing_thread_id,
            )
            return msg.message_id, existing_thread_id, chat_id
        else:
            # Create new message (thread root)
            msg = await self.app.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=keyboard,
            )
            return msg.message_id, msg.message_id, chat_id

    async def send_ack(
        self,
        chat_id: int,
        thread_id: Optional[int],
    ) -> None:
        """Send acknowledgment message."""
        if not self.app:
            return

        await self.app.bot.send_message(
            chat_id=chat_id,
            text="✅ 已收到回复，正在执行...",
            reply_to_message_id=thread_id,
        )

    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle incoming messages."""
        if not update.message or not update.effective_chat:
            return

        chat_id = update.effective_chat.id
        if not self.is_allowed_chat(chat_id):
            return

        # Get thread ID from reply
        thread_id = None
        if update.message.reply_to_message:
            thread_id = update.message.reply_to_message.message_id

        # Find session by thread
        session = None
        if thread_id:
            session = self.store.get_session_by_thread(thread_id)

        if not session:
            # Try to find any waiting session (includes chat_id=0)
            waiting = self.store.list_waiting_sessions(chat_id)
            if waiting:
                session = waiting[0]
            else:
                await update.message.reply_text(
                    "⚠️ 没有找到等待中的任务。"
                )
                return

        # Update chat_id if session was created with chat_id=0
        if session.chat_id == 0:
            self.store.update_chat_id(session.session_id, chat_id)

        # 追踪用户回复消息 ID
        if update.message.message_id:
            self.store.add_related_message(session.session_id, update.message.message_id)

        # Parse and store reply
        text = update.message.text or ""
        action, reply = self.parse_user_input(text)
        self.store.set_reply(session.session_id, reply, action)

        # Send confirmation and track the confirmation message
        if action == ActionType.DONE:
            msg = await update.message.reply_text("✅ 任务已结束")
            self.store.add_related_message(session.session_id, msg.message_id)
        elif action == ActionType.CANCEL:
            msg = await update.message.reply_text("❌ 任务已取消")
            self.store.add_related_message(session.session_id, msg.message_id)
        else:
            msg = await update.message.reply_text(
                f"📨 已发送到 Claude (#{session.short_id})"
            )
            self.store.add_related_message(session.session_id, msg.message_id)

    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle button callbacks."""
        if not update.callback_query:
            return

        query = update.callback_query
        await query.answer()

        chat_id = query.message.chat_id if query.message else None
        if not chat_id or not self.is_allowed_chat(chat_id):
            logger.warning(f"Callback from unauthorized chat: {chat_id}")
            return

        data = query.data or ""
        message_id = query.message.message_id if query.message else None
        logger.info(f"Callback received: data={data}, message_id={message_id}, chat_id={chat_id}")

        # Find session by message_id (thread_id)
        session = None
        if message_id:
            session = self.store.get_session_by_thread(message_id)
            logger.info(f"Session lookup by thread {message_id}: {session}")

        if not session:
            # Try to find by iterating all sessions (fallback)
            all_sessions = self.store.list_waiting_sessions(chat_id)
            logger.info(f"Fallback: found {len(all_sessions)} waiting sessions")
            if all_sessions:
                session = all_sessions[0]
                logger.info(f"Using first waiting session: {session.session_id}")

        if not session:
            logger.warning(f"No session found for callback, message_id={message_id}")
            await query.edit_message_text(
                query.message.text + "\n\n⚠️ Session 已过期"
            )
            return

        # Update chat_id if session was created with chat_id=0
        if session.chat_id == 0:
            self.store.update_chat_id(session.session_id, chat_id)

        # Handle different callback types
        if data == "action:done" or data == "btn:结束":
            self.store.set_reply(session.session_id, "/done", ActionType.DONE)
            logger.info(f"Session {session.session_id}: action=done")

            # 删除所有相关消息（原始通知、用户回复、确认消息等）
            deleted_count = 0
            # 先删除原始通知消息
            try:
                await query.message.delete()
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete notification message: {e}")

            # 删除所有追踪的相关消息
            related_ids = self.store.get_related_messages(session.session_id)
            for msg_id in related_ids:
                try:
                    await self.app.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete message {msg_id}: {e}")

            logger.info(f"Session {session.session_id}: deleted {deleted_count} messages")

            # Delete session from store
            self.store.delete_session(session.session_id)
            logger.info(f"Session {session.session_id}: session deleted")

        elif data == "action:continue" or data == "btn:继续":
            logger.info(f"Session {session.session_id}: waiting for input")
            msg = await query.message.reply_text(
                "💬 请输入要继续执行的指令："
            )
            # 追踪这条提示消息
            self.store.add_related_message(session.session_id, msg.message_id)

        elif data == "action:detail" or data == "btn:查看详情":
            msg = await query.message.reply_text(
                f"📋 Session: {session.session_id}\n"
                f"📁 目录: {session.cwd}\n"
                f"⏱️ 创建: {session.created_at}"
            )
            self.store.add_related_message(session.session_id, msg.message_id)

        elif data.startswith("btn:"):
            # Handle custom button - treat as continue with button text
            btn_text = data[4:]  # Remove "btn:" prefix
            action, reply = self.parse_user_input(btn_text)
            self.store.set_reply(session.session_id, reply, action)
            logger.info(f"Session {session.session_id}: custom button '{btn_text}', action={action}")

            if action == ActionType.DONE:
                # 删除所有相关消息
                deleted_count = 0
                try:
                    await query.message.delete()
                    deleted_count += 1
                except Exception:
                    pass
                related_ids = self.store.get_related_messages(session.session_id)
                for msg_id in related_ids:
                    try:
                        await self.app.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                        deleted_count += 1
                    except Exception:
                        pass
                logger.info(f"Session {session.session_id}: deleted {deleted_count} messages")
                self.store.delete_session(session.session_id)
            else:
                await query.edit_message_text(
                    query.message.text + f"\n\n📨 已发送: {btn_text}"
                )

    async def handle_status(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /status command."""
        if not update.message or not update.effective_chat:
            return

        chat_id = update.effective_chat.id
        if not self.is_allowed_chat(chat_id):
            return

        waiting = self.store.list_waiting_sessions(chat_id)
        if not waiting:
            await update.message.reply_text("✅ 没有等待中的任务")
            return

        lines = ["📋 等待中的任务:\n"]
        for s in waiting:
            lines.append(f"• #{s.short_id} - {s.cwd}")

        await update.message.reply_text("\n".join(lines))

    def setup_handlers(self, app: Application) -> None:
        """Setup message handlers."""
        app.add_handler(CommandHandler("status", self.handle_status))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_message,
            )
        )

    async def start(self) -> None:
        """Start the bot."""
        self.app = Application.builder().token(self.token).build()
        self.setup_handlers(self.app)
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

    async def stop(self) -> None:
        """Stop the bot."""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
