"""FastAPI routes for notification service."""

from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    NotifyRequest,
    NotifyResponse,
    ReplyResponse,
    AckResponse,
)
from .store import SessionStore


def create_app(
    store: Optional[SessionStore] = None,
    bot=None,
    api_key: Optional[str] = None,
) -> FastAPI:
    """Create FastAPI application."""

    app = FastAPI(
        title="Claude Code Notify",
        description="Telegram notification service for Claude Code",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store dependencies
    _store = store or SessionStore()
    _bot = bot
    _api_key = api_key

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
        try:
            # Create or get session
            session = _store.create_session(
                session_id=request.session_id,
                chat_id=0,  # Will be set by bot
                cwd=request.cwd,
            )

            # Send via bot
            if _bot:
                message_id, thread_id = await _bot.send_notification(
                    session_id=request.session_id,
                    status=request.status,
                    summary=request.summary,
                    cwd=request.cwd,
                    buttons=request.buttons,
                    existing_thread_id=session.thread_id,
                )
                _store.update_thread_id(request.session_id, message_id, thread_id)
                return NotifyResponse(
                    ok=True,
                    message_id=message_id,
                    thread_id=thread_id,
                )

            return NotifyResponse(ok=True)

        except Exception as e:
            return NotifyResponse(ok=False, error=str(e))

    @app.get("/reply/{session_id}", response_model=ReplyResponse)
    async def get_reply(
        session_id: str,
        _: str = Depends(verify_api_key),
    ):
        """Get pending reply for session."""
        session = _store.get_session(session_id)
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
        session = _store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        _store.clear_reply(session_id)

        if _bot:
            await _bot.send_ack(session.chat_id, session.thread_id)

        return AckResponse(ok=True)

    return app
