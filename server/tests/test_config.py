# server/tests/test_config.py
import os
import pytest


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("ALLOWED_CHAT_IDS", "123,456")
    monkeypatch.setenv("API_KEY", "test_key")

    # Re-import to pick up env vars
    from claude_notify.config import Settings
    settings = Settings()

    assert settings.telegram_bot_token == "test_token"
    assert settings.allowed_chat_ids == [123, 456]
    assert settings.api_key == "test_key"


def test_config_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("ALLOWED_CHAT_IDS", "123")
    monkeypatch.setenv("API_KEY", "test_key")
    # Clear PORT env var to test default value
    monkeypatch.delenv("PORT", raising=False)

    from claude_notify.config import Settings
    settings = Settings(_env_file=None)  # Ignore .env file for this test

    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.session_expiry == 86400
