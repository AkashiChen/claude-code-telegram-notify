"""Data models for Claude Code notification service."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class StatusType(str, Enum):
    """Notification status types."""
    COMPLETED = "completed"
    PERMISSION = "permission"
    IDLE = "idle"


class ActionType(str, Enum):
    """User action types."""
    CONTINUE = "continue"
    DONE = "done"
    CANCEL = "cancel"


class NotifyRequest(BaseModel):
    """Request to send a notification."""
    session_id: str = Field(..., description="Claude Code session ID")
    status: StatusType = Field(..., description="Notification status")
    summary: str = Field(..., description="Task summary")
    cwd: str = Field(..., description="Current working directory")
    buttons: Optional[list[str]] = Field(
        default=None,
        description="Optional custom buttons"
    )


class NotifyResponse(BaseModel):
    """Response after sending notification."""
    ok: bool
    thread_id: Optional[int] = None
    message_id: Optional[int] = None
    error: Optional[str] = None


class ReplyResponse(BaseModel):
    """Response when querying for reply."""
    has_reply: bool
    reply: Optional[str] = None
    action: Optional[ActionType] = None


class AckResponse(BaseModel):
    """Response after acknowledging reply."""
    ok: bool
    error: Optional[str] = None


class SessionData(BaseModel):
    """Internal session data storage."""
    session_id: str
    chat_id: int
    message_id: Optional[int] = None
    thread_id: Optional[int] = None
    cwd: str
    pending_reply: Optional[str] = None
    action: Optional[ActionType] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    # 追踪所有相关消息 ID，用于批量删除
    related_message_ids: list[int] = Field(default_factory=list)

    @property
    def short_id(self) -> str:
        """Return first 4 characters of session_id."""
        return self.session_id[:4]
