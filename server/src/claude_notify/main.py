"""Main entry point for Claude Code notification service."""

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from .api import create_app
from .bot import TelegramNotifyBot
from .config import get_settings
from .store import SessionStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Global instances
store = SessionStore()
bot: TelegramNotifyBot = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global bot
    settings = get_settings()

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


def create_main_app() -> FastAPI:
    """Create the main application."""
    settings = get_settings()
    app = create_app(
        store=store,
        bot=None,  # Will be set in lifespan
        api_key=settings.api_key,
    )
    return app


# Create app with lifespan
app = FastAPI(
    title="Claude Code Notify",
    description="Telegram notification service for Claude Code",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount the API routes
_settings = None
try:
    _settings = get_settings()
except Exception:
    pass

if _settings:
    from .api import create_app as _create_api
    _api_app = _create_api(store=store, bot=None, api_key=_settings.api_key)
    # Copy routes from api app
    app.routes.extend(_api_app.routes)


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
