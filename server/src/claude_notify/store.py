"""Session storage management."""

from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, List, Optional

from .models import SessionData, ActionType


class SessionStore:
    """Thread-safe in-memory session storage."""

    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}
        self._thread_to_session: Dict[int, str] = {}
        self._lock = Lock()

    def create_session(
        self,
        session_id: str,
        chat_id: int,
        cwd: str,
    ) -> SessionData:
        """Create or update a session."""
        with self._lock:
            if session_id in self._sessions:
                # Update existing session
                session = self._sessions[session_id]
                session.updated_at = datetime.now()
                return session

            session = SessionData(
                session_id=session_id,
                chat_id=chat_id,
                cwd=cwd,
            )
            self._sessions[session_id] = session
            return session

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID."""
        with self._lock:
            return self._sessions.get(session_id)

    def update_thread_id(
        self,
        session_id: str,
        message_id: int,
        thread_id: int,
    ) -> None:
        """Update session with thread info."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.message_id = message_id
                session.thread_id = thread_id
                session.updated_at = datetime.now()
                self._thread_to_session[thread_id] = session_id

    def set_reply(
        self,
        session_id: str,
        reply: str,
        action: ActionType,
    ) -> None:
        """Set pending reply for session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.pending_reply = reply
                session.action = action
                session.updated_at = datetime.now()

    def clear_reply(self, session_id: str) -> None:
        """Clear pending reply."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.pending_reply = None
                session.action = None
                session.updated_at = datetime.now()

    def get_session_by_thread(self, thread_id: int) -> Optional[SessionData]:
        """Get session by Telegram thread ID."""
        with self._lock:
            session_id = self._thread_to_session.get(thread_id)
            if session_id:
                return self._sessions.get(session_id)
            return None

    def cleanup_expired(self, expiry_seconds: int) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        cutoff = datetime.now() - timedelta(seconds=expiry_seconds)
        removed = 0
        with self._lock:
            expired_ids = [
                sid for sid, session in self._sessions.items()
                if session.created_at < cutoff
            ]
            for sid in expired_ids:
                session = self._sessions.pop(sid, None)
                if session and session.thread_id:
                    self._thread_to_session.pop(session.thread_id, None)
                removed += 1
        return removed

    def list_waiting_sessions(self, chat_id: int) -> List[SessionData]:
        """List sessions waiting for reply."""
        with self._lock:
            return [
                session for session in self._sessions.values()
                if session.chat_id == chat_id and session.pending_reply is None
            ]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session and session.thread_id:
                self._thread_to_session.pop(session.thread_id, None)
            return session is not None
