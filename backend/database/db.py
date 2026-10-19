"""
backend/database/db.py
───────────────────────
MySQL database setup using aiomysql.
Provides an async MySQL connection pool and table initialization.
"""

import asyncio
import json
import uuid
from urllib.parse import urlparse

import aiomysql
from backend.config import settings

# Global pool
_pool: aiomysql.Pool = None

def get_db_config():
    """Parse DATABASE_URL into aiomysql connection kwargs."""
    # mysql://root:password@localhost:3306/forensight
    parsed = urlparse(settings.DATABASE_URL)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": parsed.username,
        "password": parsed.password,
        "db": parsed.path.lstrip('/'),
        "autocommit": False,
        "cursorclass": aiomysql.DictCursor
    }

CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id VARCHAR(255) PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        display_name VARCHAR(255) NOT NULL,
        role VARCHAR(50) NOT NULL DEFAULT 'INVESTIGATOR',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS cases (
        id VARCHAR(255) PRIMARY KEY,
        case_number VARCHAR(255) UNIQUE NOT NULL,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
        created_by_name VARCHAR(255) NOT NULL DEFAULT 'System',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS evidence (
        id VARCHAR(255) PRIMARY KEY,
        case_id VARCHAR(255) NOT NULL,
        file_name VARCHAR(255) NOT NULL,
        file_type VARCHAR(50) NOT NULL,
        file_path VARCHAR(255) NOT NULL,
        file_size BIGINT NOT NULL,
        mime_type VARCHAR(100) NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
        uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP NULL,
        transcription_status VARCHAR(50) DEFAULT 'PENDING',
        transcript TEXT,
        FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS detections (
        id VARCHAR(255) PRIMARY KEY,
        evidence_id VARCHAR(255) NOT NULL,
        label VARCHAR(255) NOT NULL,
        confidence FLOAT NOT NULL,
        bounding_box TEXT NOT NULL,
        frame_timestamp FLOAT,
        grad_cam_path VARCHAR(255),
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS text_chunks (
        id VARCHAR(255) PRIMARY KEY,
        evidence_id VARCHAR(255) NOT NULL,
        chunk_index INT NOT NULL,
        content TEXT NOT NULL,
        source_type VARCHAR(50) NOT NULL,
        page_number INT,
        start_time FLOAT,
        end_time FLOAT,
        vector_id VARCHAR(255),
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id VARCHAR(255) PRIMARY KEY,
        action VARCHAR(255) NOT NULL,
        metadata TEXT,
        ip_address VARCHAR(255),
        user_id VARCHAR(255),
        case_id VARCHAR(255),
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
]


# (table, column, DDL) — columns added after the original schema shipped.
# `detections` doubles as the store for operator-driven VLM ROI findings; the
# `source` column distinguishes them from automatic detector output.
_COLUMN_MIGRATIONS = [
    ("evidence", "file_hash_sha256", "CHAR(64) NULL"),
    ("detections", "source", "VARCHAR(30) NOT NULL DEFAULT 'DETECTOR'"),
    ("detections", "category", "VARCHAR(30) NULL"),
    ("detections", "readout_text", "TEXT NULL"),
    ("detections", "details_json", "TEXT NULL"),
    ("detections", "lexicon_compliant", "TINYINT(1) NOT NULL DEFAULT 1"),
    ("detections", "frame_index", "INT NULL"),
    ("detections", "timestamp_str", "VARCHAR(20) NULL"),
    ("detections", "frame_sha256", "CHAR(64) NULL"),
    ("detections", "crop_sha256", "CHAR(64) NULL"),
    ("detections", "operator_id", "VARCHAR(100) NULL"),
    ("detections", "verification_status", "VARCHAR(30) NOT NULL DEFAULT 'Unverified_Draft'"),
    ("detections", "verified_by", "VARCHAR(100) NULL"),
    ("detections", "verified_at", "VARCHAR(40) NULL"),
    ("detections", "audit_seq", "BIGINT NULL"),
    ("detections", "role", "VARCHAR(20) NULL"),
    ("detections", "subject_name", "VARCHAR(120) NULL"),
    ("text_chunks", "wall_time", "VARCHAR(40) NULL"),
    ("text_chunks", "speaker", "VARCHAR(80) NULL"),
    ("evidence", "recording_start", "VARCHAR(40) NULL"),
    ("evidence", "recording_start_source", "VARCHAR(30) NULL"),
    ("detections", "class_name", "VARCHAR(60) NULL"),
    ("detections", "track_key", "VARCHAR(40) NULL"),
    ("evidence", "latitude", "DOUBLE NULL"),
    ("evidence", "longitude", "DOUBLE NULL"),
    ("evidence", "location_label", "VARCHAR(255) NULL"),
    ("evidence", "captured_at", "VARCHAR(40) NULL"),
    ("evidence", "analysis_status", "VARCHAR(30) NOT NULL DEFAULT 'NOT_RUN'"),
    ("evidence", "analysis_message", "TEXT NULL"),
    ("evidence", "analysis_progress", "INT NOT NULL DEFAULT 0"),
]

# Observable tokens (plates, phones, objects …) extracted automatically from
# evidence; the raw material for cross-evidence correlation.
CLUES_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS clues (
        id           VARCHAR(64) PRIMARY KEY,
        case_id      VARCHAR(255) NOT NULL,
        evidence_id  VARCHAR(255) NOT NULL,
        kind         VARCHAR(20)  NOT NULL,
        value        VARCHAR(500) NOT NULL,
        norm_value   VARCHAR(500) NOT NULL,
        confidence   FLOAT NOT NULL DEFAULT 0,
        source       VARCHAR(30)  NOT NULL,
        timestamp_ms BIGINT NULL,
        bbox         VARCHAR(100) NULL,
        context      TEXT NULL,
        created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_clues_case (case_id),
        INDEX idx_clues_evidence (evidence_id),
        FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE
    );
"""


async def _ensure_columns(cur) -> None:
    """Add any missing migration columns (idempotent)."""
    for table, column, ddl in _COLUMN_MIGRATIONS:
        await cur.execute(
            "SELECT COUNT(*) AS n FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
            (table, column),
        )
        row = await cur.fetchone()
        exists = int(row["n"] if isinstance(row, dict) else row[0]) > 0
        if not exists:
            await cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


# The investigator's own decisions about who is who in a case. Kept apart from evidence-derived
# data: a role here is always a human designation, attributed and timestamped.
DESIGNATIONS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS person_designations (
        id            VARCHAR(64)  PRIMARY KEY,
        case_id       VARCHAR(255) NOT NULL,
        person_key    VARCHAR(190) NOT NULL,
        display_name  VARCHAR(190) NOT NULL,
        role          VARCHAR(30)  NOT NULL DEFAULT 'UNASSIGNED',
        basis         TEXT NULL,
        aliases       TEXT NULL,
        is_manual     TINYINT(1)   NOT NULL DEFAULT 0,
        designated_by VARCHAR(100) NULL,
        designated_at VARCHAR(40)  NULL,
        created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_case_person (case_id, person_key)
    );
"""


async def init_db() -> None:
    """Create DB tables on startup using aiomysql."""
    global _pool
    config = get_db_config()
    _pool = await aiomysql.create_pool(**config, minsize=1, maxsize=10)
    
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            for query in CREATE_TABLES_SQL:
                await cur.execute(query)
            # Additive migrations for databases created before the forensic
            # ROI-inspection feature (CREATE TABLE IF NOT EXISTS won't add columns).
            await _ensure_columns(cur)
            await cur.execute(CLUES_TABLE_SQL)
            await cur.execute(DESIGNATIONS_TABLE_SQL)
            # Hash-chained, append-only chain-of-custody log.
            from backend.modules import audit_engine
            await audit_engine.ensure_schema(cur)
        await conn.commit()
    print(f"[DB] MySQL initialised for db: {config['db']}")


class _DBContextManager:
    """A context manager compatible with both 'await get_db()' usage in current codebase,
    which exposes execute(), commit(), close() and fetchall/fetchone behavior directly
    if needed by the app."""
    
    def __init__(self, conn, cursor):
        self.conn = conn
        self.cursor = cursor
        
    async def execute(self, query, args=None):
        await self.cursor.execute(query, args)
        return self.cursor

    async def commit(self):
        await self.conn.commit()
        
    async def close(self):
        await self.cursor.close()
        global _pool
        if _pool:
            _pool.release(self.conn)
        else:
            self.conn.close()


async def get_db():
    """Open a short-lived connection wrapper for a single request."""
    global _pool
    if _pool is None:
        config = get_db_config()
        _pool = await aiomysql.create_pool(**config, minsize=1, maxsize=10)
    
    conn = await _pool.acquire()
    cursor = await conn.cursor()
    return _DBContextManager(conn, cursor)


async def write_audit_log(
    action: str,
    case_id: str | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
    evidence_id: str | None = None,
    file_hash_sha256: str | None = None,
    operator_id: str = "SYSTEM",
) -> None:
    """
    Record an audit event.

    Writes the legacy `audit_logs` row (kept for existing dashboards) and
    appends the same event to the tamper-evident `audit_trail` hash chain.
    """
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO audit_logs (id, action, case_id, metadata, ip_address)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                str(uuid.uuid4()).replace("-", ""),
                action,
                case_id,
                json.dumps(metadata) if metadata else None,
                ip_address,
            ),
        )
        await db.commit()
    finally:
        await db.close()

    from backend.modules import audit_engine
    chain_meta = dict(metadata or {})
    if ip_address:
        chain_meta["ip_address"] = ip_address
    await audit_engine.append_entry(
        action,
        operator_id=operator_id,
        case_id=case_id,
        evidence_id=evidence_id or chain_meta.get("evidence_id"),
        file_hash_sha256=file_hash_sha256,
        metadata=chain_meta,
    )
