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


async def init_db() -> None:
    """Create DB tables on startup using aiomysql."""
    global _pool
    config = get_db_config()
    _pool = await aiomysql.create_pool(**config, minsize=1, maxsize=10)
    
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            for query in CREATE_TABLES_SQL:
                await cur.execute(query)
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
) -> None:
    """Insert an immutable audit log entry."""
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
