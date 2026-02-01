"""Configuration management."""

from functools import lru_cache
from typing import List, Union

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Telegram
    telegram_bot_token: str
    allowed_chat_ids: Union[str, List[int]]

    # API Security
    api_key: str

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Session
    session_expiry: int = 86400  # 24 hours

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @model_validator(mode="before")
    @classmethod
    def parse_chat_ids(cls, values):
        """Parse comma-separated chat IDs string into list of integers."""
        if isinstance(values, dict):
            chat_ids = values.get("allowed_chat_ids")
            if isinstance(chat_ids, str):
                values["allowed_chat_ids"] = [
                    int(x.strip()) for x in chat_ids.split(",")
                ]
            elif isinstance(chat_ids, int):
                values["allowed_chat_ids"] = [chat_ids]
        return values


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
