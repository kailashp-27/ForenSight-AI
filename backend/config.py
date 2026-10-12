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
    YOLO_MODEL: str = "backend/storage/models/yolov8s.pt"
    AUTO_SAMPLE_INTERVAL_S: float = 1.0   # legacy fixed-interval sampler (benchmark baseline)
    AUTO_MAX_FRAMES: int = 90             # legacy sampler frame cap

    # Tracking pipeline (default for video)
    AUTO_DETECT_FPS: float = 3.0          # detection+tracking rate (frames per second of video)
    AUTO_MAX_DETECT_FRAMES: int = 450     # cap on detected frames per video (stride stretches)
    AUTO_IMGSZ: int = 960                 # inference size; larger finds smaller objects
    AUTO_MIN_TRACK_FRAMES: int = 2        # tracks shorter than this are treated as flicker
    AUTO_CROPS_PER_TRACK: int = 5         # sharpest/largest crops kept per track for OCR
    AUTO_SCENE_OCR_INTERVAL_S: float = 1.0
    AUTO_SCENE_OCR_MAX: int = 90
    AUTO_SCENE_FRAMES_PER_WINDOW: int = 2   # sharpest N frames OCR'd per window
    USE_GPU: bool = True                  # use CUDA when available
    OCR_ENSEMBLE: bool = True             # second OCR engine (RapidOCR) votes with EasyOCR
    AUTO_MAX_PLATE_OCR: int = 60          # cap on OCR calls over vehicle/plate crops

    # Open-vocabulary detector (YOLO-World): extra forensic classes with NO training.
    OPEN_VOCAB_ENABLED: bool = True
    OPEN_VOCAB_MODEL: str = "backend/storage/models/yolov8s-worldv2.pt"
    OPEN_VOCAB_CLASSES: str = "license plate,knife,crowbar,hammer,backpack,duffel bag,helmet,face mask,gloves,gun"
    OPEN_VOCAB_CONF: float = 0.30

    # ── Chain of custody ───────────────────────────────────────────────────────
    # AES-256-GCM key used to encrypt raw VLM payloads stored in audit_trail.
    # Auto-generated on first run. Back it up: losing it makes stored payloads
    # unrecoverable. The default sits under storage/, which is gitignored.
    AUDIT_KEY_PATH: str = "backend/storage/.audit.key"
    # Seconds within which two findings in one clip are linked "co_occurs".
    GRAPH_COOCCURRENCE_WINDOW_S: float = 10.0


# Singleton instance — import this everywhere
settings = Settings()
