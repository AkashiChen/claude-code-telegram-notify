"""Main entry point for Claude Code notification service."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Header

from .bot import TelegramNotifyBot
from .config import get_settings
from .store import SessionStore
from .models import (
    NotifyRequest,
    NotifyResponse,
    ReplyResponse,
    AckResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Global instances
store = SessionStore()
bot: Optional[TelegramNotifyBot] = None
_api_key: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global bot, _api_key
    settings = get_settings()
    _api_key = settings.api_key

    # Start Telegram bot
    bot = TelegramNotifyBot(
        token=settings.telegram_bot_token,
        allowed_chat_ids=settings.allowed_chat_ids,
        store=store,
    )
    await bot.start()
    logger.info("Telegram bot started")

    # Start cleanup task
    cleanup_task = asyncio.create_task(cleanup_loop(settings.session_expiry))

    yield

    # Cleanup
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    await bot.stop()
    logger.info("Telegram bot stopped")


async def cleanup_loop(expiry_seconds: int):
    """Periodically cleanup expired sessions."""
    while True:
        await asyncio.sleep(3600)  # Every hour
        removed = store.cleanup_expired(expiry_seconds)
        if removed:
            logger.info(f"Cleaned up {removed} expired sessions")


# Create app with lifespan
app = FastAPI(
    title="Claude Code Notify",
    description="Telegram notification service for Claude Code",
    version="0.1.0",
    lifespan=lifespan,
)


def verify_api_key(authorization: Optional[str] = Header(None)):
    """Verify API key from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization")

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    if parts[1] != _api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return parts[1]


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/notify", response_model=NotifyResponse)
async def notify(
    request: NotifyRequest,
    _: str = Depends(verify_api_key),
):
    """Send notification to Telegram."""
    global bot
    try:
        # Create or get session
        session = store.create_session(
            session_id=request.session_id,
            chat_id=0,  # Will be set by bot
            cwd=request.cwd,
        )

        # Send via bot
        if bot:
            logger.info(f"Sending notification for session {request.session_id}")
            message_id, thread_id, chat_id = await bot.send_notification(
                session_id=request.session_id,
                status=request.status,
                summary=request.summary,
                cwd=request.cwd,
                buttons=request.buttons,
                existing_thread_id=session.thread_id,
            )
            store.update_thread_id(request.session_id, message_id, thread_id, chat_id)
            logger.info(f"Notification sent: message_id={message_id}, thread_id={thread_id}, chat_id={chat_id}")
            return NotifyResponse(
                ok=True,
                message_id=message_id,
                thread_id=thread_id,
            )
        else:
            logger.warning("Bot not initialized, notification not sent")

        return NotifyResponse(ok=True)

    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return NotifyResponse(ok=False, error=str(e))


@app.get("/reply/{session_id}", response_model=ReplyResponse)
async def get_reply(
    session_id: str,
    _: str = Depends(verify_api_key),
):
    """Get pending reply for session."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.pending_reply:
        return ReplyResponse(
            has_reply=True,
            reply=session.pending_reply,
            action=session.action,
        )
    return ReplyResponse(has_reply=False)


@app.post("/ack/{session_id}", response_model=AckResponse)
async def ack_reply(
    session_id: str,
    _: str = Depends(verify_api_key),
):
    """Acknowledge receipt of reply."""
    global bot
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    store.clear_reply(session_id)

    if bot:
        await bot.send_ack(session.chat_id, session.thread_id)

    return AckResponse(ok=True)


def main():
    """Run the server."""
    settings = get_settings()
    uvicorn.run(
        "claude_notify.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
