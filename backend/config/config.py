"""
novaTech AI Customer Support — Central Configuration Module

All AI components import model settings from this module.
To change the model, edit only this file (or the .env).
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Nexus API ────────────────────────────────────────────
    nexus_api_key: str = "nexus_demo_key_12345"
    nexus_base_url: str = "https://api.nexus.ai/v1"

    # ── Model Configuration ──────────────────────────────────
    # CHAT_MODEL is the canonical name; MODEL_NAME is the legacy alias
    chat_model: str = "nexus-gpt-4o"
    model_name: str = ""          # legacy alias — do not use directly
    embedding_model: str = "nexus-text-embedding-3"
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.9

    # ── Qdrant ───────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_storage_path: str = "./qdrant_storage"
    qdrant_collection_name: str = "novacart_knowledge"

    # ── Database ─────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./app.db"

    # ── Authentication ───────────────────────────────────────
    jwt_secret: str = "novacart_super_secret_jwt_key_change_in_production_2024"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # ── Server ───────────────────────────────────────────────
    port: int = 8000
    host: str = "0.0.0.0"
    debug: bool = True
    frontend_url: str = "http://localhost:3000"

    @property
    def effective_chat_model(self) -> str:
        """Return CHAT_MODEL, falling back to MODEL_NAME for backward compatibility."""
        if self.model_name and not self.chat_model:
            return self.model_name
        return self.chat_model

    @property
    def effective_api_key(self) -> str:
        """Return the API key for LLM calls."""
        return self.nexus_api_key

    @property
    def effective_base_url(self) -> str:
        """Return the base URL for LLM calls."""
        return self.nexus_base_url

    @property
    def openai_client_kwargs(self) -> dict:
        """Keyword args for OpenAI-compatible client pointing at Nexus."""
        return {
            "api_key": self.nexus_api_key,
            "base_url": self.nexus_base_url,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# Module-level convenience accessor
settings: Settings = get_settings()
