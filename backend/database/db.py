"""
backend/database/db.py
───────────────────────
SQLite database setup using aiosqlite directly (no Prisma required for SQLite dev).
Provides a lightweight async SQLite connection pool and table initialization.

Switch to PostgreSQL + Prisma when moving to production:
  1. Set DATABASE_URL to a postgres:// URL in .env
  2. Run: prisma generate && prisma db push
"""

import aiosqlite
import asyncio
from pathlib import Path
from backend.config import settings

DB_PATH = Path(settings.SQLITE_PATH)


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'INVESTIGATOR',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    case_number TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN',
    created_by_name TEXT NOT NULL DEFAULT 'System',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    case_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    processed_at TEXT,
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS detections (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    evidence_id TEXT NOT NULL,
    label TEXT NOT NULL,
    confidence REAL NOT NULL,
    bounding_box TEXT NOT NULL,
    frame_timestamp REAL,
    grad_cam_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS text_chunks (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    evidence_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    source_type TEXT NOT NULL,
    page_number INTEGER,
    start_time REAL,
    end_time REAL,
    vector_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    action TEXT NOT NULL,
    metadata TEXT,
    ip_address TEXT,
    user_id TEXT,
    case_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


async def init_db() -> None:
    """Create DB file and all tables on startup."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await db.commit()
    print(f"[DB] SQLite initialised at {DB_PATH}")


async def get_db() -> aiosqlite.Connection:
    """Open a short-lived connection for a single request."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def write_audit_log(
    action: str,
    case_id: str | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Insert an immutable audit log entry."""
    import json, uuid
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO audit_logs (id, action, case_id, metadata, ip_address)
               VALUES (?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()).replace("-", ""),
                action,
                case_id,
                json.dumps(metadata) if metadata else None,
                ip_address,
            ),
        )
        await db.commit()
