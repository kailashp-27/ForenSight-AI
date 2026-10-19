"""
backend/modules/audit_engine.py
───────────────────────────────
Immutable chain-of-custody log (the `audit_trail` table).

Tamper evidence is layered:
  1. Database triggers reject UPDATE and DELETE on audit_trail (append-only).
  2. Every row stores `prev_hash` and `entry_hash`, where
         entry_hash = SHA-256( prev_hash ‖ entry fields )
     so altering or removing ANY historical row breaks every later hash.
     `verify_chain()` recomputes the whole chain and pinpoints the first
     broken row — this still detects tampering by someone who bypasses the
     triggers (e.g. a DBA with direct table access).
  3. Writers are serialised through a one-row `audit_chain_head` table locked
     with SELECT … FOR UPDATE, so concurrent requests can never fork the chain.

Sensitive raw model output is additionally encrypted at rest with
AES-256-GCM (`encrypt_payload`); the ciphertext — not the plaintext — is what
gets hashed into the chain.

The hashing / verification / encryption helpers are pure functions so they can
be tested without a database.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.config import settings

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64

# ── DDL (executed from init_db) ──────────────────────────────────────────────

AUDIT_TABLES_SQL: List[str] = [
    """
    CREATE TABLE IF NOT EXISTS audit_trail (
        seq               BIGINT AUTO_INCREMENT PRIMARY KEY,
        case_id           VARCHAR(255) NULL,
        evidence_id       VARCHAR(255) NULL,
        file_hash_sha256  CHAR(64)     NULL,
        operator_id       VARCHAR(100) NOT NULL,
        action            VARCHAR(100) NOT NULL,
        timestamp_utc     VARCHAR(40)  NOT NULL,
        metadata_json     LONGTEXT     NOT NULL,
        prev_hash         CHAR(64)     NOT NULL,
        entry_hash        CHAR(64)     NOT NULL,
        INDEX idx_audit_case (case_id),
        INDEX idx_audit_evidence (evidence_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_chain_head (
        id        TINYINT PRIMARY KEY,
        last_seq  BIGINT   NOT NULL,
        last_hash CHAR(64) NOT NULL
    );
    """,
]

_TRIGGERS = {
    "audit_trail_no_update": (
        "CREATE TRIGGER audit_trail_no_update BEFORE UPDATE ON audit_trail "
        "FOR EACH ROW SIGNAL SQLSTATE '45000' "
        "SET MESSAGE_TEXT = 'audit_trail is append-only: UPDATE is forbidden'"
    ),
    "audit_trail_no_delete": (
        "CREATE TRIGGER audit_trail_no_delete BEFORE DELETE ON audit_trail "
        "FOR EACH ROW SIGNAL SQLSTATE '45000' "
        "SET MESSAGE_TEXT = 'audit_trail is append-only: DELETE is forbidden'"
    ),
}


async def ensure_schema(cur) -> None:
    """Create tables, seed the chain head and install append-only triggers."""
    for ddl in AUDIT_TABLES_SQL:
        await cur.execute(ddl)

    await cur.execute(
        "INSERT IGNORE INTO audit_chain_head (id, last_seq, last_hash) VALUES (1, 0, %s)",
        (GENESIS_HASH,),
    )

    for name, ddl in _TRIGGERS.items():
        await cur.execute(
            "SELECT COUNT(*) AS n FROM information_schema.TRIGGERS "
            "WHERE TRIGGER_SCHEMA = DATABASE() AND TRIGGER_NAME = %s",
            (name,),
        )
        row = await cur.fetchone()
        if row and int(list(row.values())[0] if isinstance(row, dict) else row[0]) > 0:
            continue
        try:
            await cur.execute(ddl)
        except Exception as exc:  # insufficient TRIGGER privilege / binlog policy
            # The hash chain still makes tampering detectable via verify_chain().
            logger.warning("Could not install trigger %s: %s", name, exc)


# ── pure helpers (hashing, canonicalisation, verification) ───────────────────

def utc_now_iso() -> str:
    """Fixed-width UTC timestamp so the stored string round-trips exactly."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def compute_entry_hash(
    prev_hash: str,
    case_id: Optional[str],
    evidence_id: Optional[str],
    file_hash_sha256: Optional[str],
    operator_id: str,
    action: str,
    timestamp_utc: str,
    metadata_json: str,
) -> str:
    # A JSON array (not string concatenation) so field boundaries are unambiguous.
    blob = json.dumps(
        [prev_hash, case_id, evidence_id, file_hash_sha256, operator_id, action,
         timestamp_utc, metadata_json],
        ensure_ascii=True, separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class ChainReport:
    ok: bool
    entries_checked: int
    broken_at_seq: Optional[int] = None
    reason: Optional[str] = None
    head_seq: int = 0
    head_hash: str = GENESIS_HASH
    notes: List[str] = field(default_factory=list)


def verify_rows(rows: Sequence[Dict[str, Any]], expected_head_hash: Optional[str] = None) -> ChainReport:
    """
    Recompute a chain from rows ordered by `seq`.

    Detects: edited fields, deleted rows, inserted/reordered rows, and a head
    pointer that disagrees with the last row (tail truncation).
    """
    prev = GENESIS_HASH
    last_seq = 0
    for row in rows:
        seq = int(row["seq"])
        if row["prev_hash"] != prev:
            return ChainReport(False, 0, seq, "prev_hash does not match previous entry (row removed, inserted or reordered)")
        recomputed = compute_entry_hash(
            row["prev_hash"], row.get("case_id"), row.get("evidence_id"),
            row.get("file_hash_sha256"), row["operator_id"], row["action"],
            row["timestamp_utc"], row["metadata_json"],
        )
        if recomputed != row["entry_hash"]:
            return ChainReport(False, 0, seq, "entry_hash mismatch (row contents were modified)")
        prev = row["entry_hash"]
        last_seq = seq

    report = ChainReport(True, len(rows), head_seq=last_seq, head_hash=prev)
    if expected_head_hash is not None and expected_head_hash != prev:
        report.ok = False
        report.reason = "chain head pointer disagrees with last row (trailing rows removed)"
        report.broken_at_seq = last_seq
    return report


# ── payload encryption (AES-256-GCM) ─────────────────────────────────────────

_key_cache: Optional[bytes] = None


def _load_key() -> bytes:
    global _key_cache
    if _key_cache is not None:
        return _key_cache
    path = Path(settings.AUDIT_KEY_PATH)
    if path.exists():
        key = base64.b64decode(path.read_text().strip())
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        key = AESGCM.generate_key(bit_length=256)
        path.write_text(base64.b64encode(key).decode("ascii"))
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        logger.warning("Generated new audit encryption key at %s — back it up.", path)
    if len(key) != 32:
        raise RuntimeError(f"Audit key at {path} is not a 256-bit key")
    _key_cache = key
    return key


def encrypt_payload(plaintext: str, aad: str = "") -> Dict[str, str]:
    nonce = os.urandom(12)
    ct = AESGCM(_load_key()).encrypt(nonce, plaintext.encode("utf-8"), aad.encode("utf-8"))
    return {
        "alg": "AES-256-GCM",
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ct).decode("ascii"),
        "aad": aad,
    }


def decrypt_payload(blob: Dict[str, str]) -> str:
    nonce = base64.b64decode(blob["nonce_b64"])
    ct = base64.b64decode(blob["ciphertext_b64"])
    return AESGCM(_load_key()).decrypt(nonce, ct, blob.get("aad", "").encode("utf-8")).decode("utf-8")


# ── database operations ──────────────────────────────────────────────────────

async def _release_read(db) -> None:
    """End the implicit read transaction so a pooled connection never serves a stale snapshot."""
    try:
        await db.commit()
    finally:
        await db.close()


async def append_entry(
    action: str,
    *,
    operator_id: str = "SYSTEM",
    case_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
    file_hash_sha256: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Append one entry to the chain inside a single transaction.

    The head row is locked for the duration, which serialises writers and
    guarantees seq order == chain order.
    """
    from backend.database.db import get_db  # local import: avoid import cycle

    if file_hash_sha256 is not None and len(file_hash_sha256) != 64:
        raise ValueError("file_hash_sha256 must be a 64-char hex SHA-256 digest")

    timestamp_utc = utc_now_iso()
    metadata_json = canonical_json(metadata or {})

    db = await get_db()
    try:
        cur = await db.execute("SELECT last_hash FROM audit_chain_head WHERE id = 1 FOR UPDATE")
        head = await cur.fetchone()
        if head is None:
            raise RuntimeError("audit_chain_head is not initialised")
        prev_hash = head["last_hash"]

        entry_hash = compute_entry_hash(
            prev_hash, case_id, evidence_id, file_hash_sha256,
            operator_id, action, timestamp_utc, metadata_json,
        )
        cur = await db.execute(
            """INSERT INTO audit_trail
               (case_id, evidence_id, file_hash_sha256, operator_id, action,
                timestamp_utc, metadata_json, prev_hash, entry_hash)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (case_id, evidence_id, file_hash_sha256, operator_id, action,
             timestamp_utc, metadata_json, prev_hash, entry_hash),
        )
        seq = cur.lastrowid
        await db.execute(
            "UPDATE audit_chain_head SET last_seq = %s, last_hash = %s WHERE id = 1",
            (seq, entry_hash),
        )
        await db.commit()
    except Exception:
        await db.conn.rollback()
        raise
    finally:
        await db.close()

    return {"seq": seq, "entry_hash": entry_hash, "prev_hash": prev_hash, "timestamp_utc": timestamp_utc}


async def list_entries(
    limit: int = 100,
    offset: int = 0,
    case_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    from backend.database.db import get_db

    where, args = [], []
    if case_id:
        where.append("case_id = %s")
        args.append(case_id)
    if evidence_id:
        where.append("evidence_id = %s")
        args.append(evidence_id)
    clause = f"WHERE {' AND '.join(where)}" if where else ""

    db = await get_db()
    try:
        cur = await db.execute(
            f"SELECT * FROM audit_trail {clause} ORDER BY seq DESC LIMIT %s OFFSET %s",
            (*args, int(limit), int(offset)),
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await _release_read(db)


async def get_entry(seq: int) -> Optional[Dict[str, Any]]:
    from backend.database.db import get_db

    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM audit_trail WHERE seq = %s", (seq,))
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await _release_read(db)


async def verify_chain() -> ChainReport:
    from backend.database.db import get_db

    db = await get_db()
    try:
        head_cur = await db.execute("SELECT last_hash FROM audit_chain_head WHERE id = 1")
        head = await head_cur.fetchone()
        cur = await db.execute("SELECT * FROM audit_trail ORDER BY seq ASC")
        rows = [dict(r) for r in await cur.fetchall()]
    finally:
        await _release_read(db)

    return verify_rows(rows, expected_head_hash=head["last_hash"] if head else None)
