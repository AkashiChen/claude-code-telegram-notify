# server/tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("ALLOWED_CHAT_IDS", "12345")
    monkeypatch.setenv("API_KEY", "test_api_key")
