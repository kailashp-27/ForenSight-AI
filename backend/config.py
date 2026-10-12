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
    DATABASE_URL: str = "mysql://root:Priya2711!@localhost:3306/forensight"
    # SQLite path used during local development (no PostgreSQL/MySQL required)
    SQLITE_PATH: str = "backend/database/forensight.db"

    # ── Storage ────────────────────────────────────────────────────────────────
    STORAGE_DIR: str = "backend/storage"

    # ── Socket.io / CORS ───────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]  # Vite dev server

    # ── Ollama (local LLM) ─────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:1b"

    # ── Local vision-language model (ROI inspection) ───────────────────────────
    # Must be a vision-capable model already pulled into the local Ollama
    # (e.g. `ollama pull qwen2.5vl:7b`). The endpoint host is validated to be
    # loopback-only in vlm_client.py — the air-gap rule is enforced in code.
    OLLAMA_VISION_MODEL: str = "qwen2.5vl:7b"
    # Cold model loads can take 30-60s before generation starts.
    VLM_TIMEOUT_S: float = 180.0
    VLM_MAX_TOKENS: int = 250

    # ── Automatic analysis (YOLO + OCR) ────────────────────────────────────────
    # Pre-trained COCO weights; downloaded once, then fully offline.
    YOLO_MODEL: str = "backend/storage/models/yolov8n.pt"
    AUTO_SAMPLE_INTERVAL_S: float = 1.0   # video sampling period (stretched for long clips)
    AUTO_MAX_FRAMES: int = 90             # hard cap on analysed frames per video

    # ── Chain of custody ───────────────────────────────────────────────────────
    # AES-256-GCM key used to encrypt raw VLM payloads stored in audit_trail.
    # Auto-generated on first run. Back it up: losing it makes stored payloads
    # unrecoverable. The default sits under storage/, which is gitignored.
    AUDIT_KEY_PATH: str = "backend/storage/.audit.key"
    # Seconds within which two findings in one clip are linked "co_occurs".
    GRAPH_COOCCURRENCE_WINDOW_S: float = 10.0


# Singleton instance — import this everywhere
settings = Settings()
