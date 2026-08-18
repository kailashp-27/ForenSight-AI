"""
config.py
─────────
Centralised application settings loaded from a .env file.
All modules should import `settings` from here — never read os.environ directly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ────────────────────────────────────────────────────────────
    APP_NAME: str = "ForenSight AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ── Database ───────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/forensight"

    # ── Storage ────────────────────────────────────────────────────────────────
    STORAGE_DIR: str = "backend/storage"

    # ── Socket.io / CORS ───────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]  # Vite dev server

    # ── Ollama (local LLM) ─────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"


# Singleton instance — import this everywhere
settings = Settings()
