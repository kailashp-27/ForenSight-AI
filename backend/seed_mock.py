#!/usr/bin/env python3
"""
backend/seed_mock.py
────────────────────
Seeds one realistic demo case with 4 evidence files into the MySQL database.

Usage (from project root):
    python -m backend.seed_mock

Make sure the backend is NOT running so there are no connection conflicts,
or simply run it standalone — it opens its own pool.
"""

import asyncio
import uuid
from datetime import datetime, timedelta

import aiomysql
from backend.config import settings
from urllib.parse import urlparse


def _make_id() -> str:
    return str(uuid.uuid4()).replace("-", "")


def _parse_db():
    p = urlparse(settings.DATABASE_URL)
    return {
        "host":        p.hostname,
        "port":        p.port or 3306,
        "user":        p.username,
        "password":    p.password,
        "db":          p.path.lstrip("/"),
        "autocommit":  False,
        "cursorclass": aiomysql.DictCursor,
    }


# ── Demo case ────────────────────────────────────────────────────────────────
CASE_ID     = _make_id()
CASE_NUMBER = "CASE-2026-001"

CASE = {
    "id":               CASE_ID,
    "case_number":      CASE_NUMBER,
    "title":            "Downtown Fraud Investigation — Aug 2026",
    "description": (
        "Multi-layered fraud investigation involving suspected account takeover, "
        "structured cash transactions (smurfing), and a CCTV incident at Lobby B. "
        "Involves cross-analysis of financial records, CCTV footage, and audio interviews."
    ),
    "status":           "UNDER_REVIEW",
    "created_by_name":  "Kailash P",
}

# ── Demo evidence files ───────────────────────────────────────────────────────
now = datetime.utcnow()

EVIDENCE = [
    {
        "id":        _make_id(),
        "case_id":   CASE_ID,
        "file_name": "CCTV_lobby_aug19.mp4",
        "file_type": "VIDEO",
        "file_path": "storage/CASE-2026-001/CCTV_lobby_aug19.mp4",
        "file_size": 248_300_000,   # ~248 MB
        "mime_type": "video/mp4",
        "status":    "COMPLETED",
        "uploaded_at": (now - timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S"),
        "processed_at": (now - timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S"),
    },
    {
        "id":        _make_id(),
        "case_id":   CASE_ID,
        "file_name": "bank_statement_ACC887_aug.pdf",
        "file_type": "DOCUMENT",
        "file_path": "storage/CASE-2026-001/bank_statement_ACC887_aug.pdf",
        "file_size": 1_240_000,     # ~1.2 MB
        "mime_type": "application/pdf",
        "status":    "COMPLETED",
        "uploaded_at": (now - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
        "processed_at": (now - timedelta(hours=7, minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
    },
    {
        "id":        _make_id(),
        "case_id":   CASE_ID,
        "file_name": "interview_suspect_kp2234.wav",
        "file_type": "AUDIO",
        "file_path": "storage/CASE-2026-001/interview_suspect_kp2234.wav",
        "file_size": 52_400_000,    # ~52 MB
        "mime_type": "audio/wav",
        "status":    "PROCESSING",
        "uploaded_at": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
        "processed_at": None,
    },
    {
        "id":        _make_id(),
        "case_id":   CASE_ID,
        "file_name": "scene_photo_lobby_B.jpg",
        "file_type": "IMAGE",
        "file_path": "storage/CASE-2026-001/scene_photo_lobby_B.jpg",
        "file_size": 4_800_000,     # ~4.8 MB
        "mime_type": "image/jpeg",
        "status":    "COMPLETED",
        "uploaded_at": (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
        "processed_at": (now - timedelta(hours=5, minutes=45)).strftime("%Y-%m-%d %H:%M:%S"),
    },
]

# ── Demo YOLOv8 detection (for the CCTV video) ───────────────────────────────
DETECTIONS = [
    {
        "id":              _make_id(),
        "evidence_id":     EVIDENCE[0]["id"],  # CCTV video
        "label":           "firearm",
        "confidence":      0.783,
        "bounding_box":    '{"x": 412, "y": 280, "w": 64, "h": 48}',
        "frame_timestamp": 134.5,              # seconds into the video
        "grad_cam_path":   "storage/CASE-2026-001/gradcam/frame_3260_heatmap.png",
    },
    {
        "id":              _make_id(),
        "evidence_id":     EVIDENCE[0]["id"],
        "label":           "person",
        "confidence":      0.961,
        "bounding_box":    '{"x": 380, "y": 120, "w": 120, "h": 260}',
        "frame_timestamp": 134.5,
        "grad_cam_path":   None,
    },
]

# ── Audit log entries ─────────────────────────────────────────────────────────
AUDIT_LOGS = [
    {
        "id": _make_id(), "action": "CASE_CREATED",
        "case_id": CASE_ID,
        "metadata": f'{{"case_number": "{CASE_NUMBER}", "created_by": "Kailash P"}}',
        "ip_address": "127.0.0.1",
    },
    {
        "id": _make_id(), "action": "EVIDENCE_UPLOADED",
        "case_id": CASE_ID,
        "metadata": '{"file": "CCTV_lobby_aug19.mp4", "size_mb": 248}',
        "ip_address": "127.0.0.1",
    },
    {
        "id": _make_id(), "action": "YOLO_DETECTION_COMPLETED",
        "case_id": CASE_ID,
        "metadata": '{"detections": 2, "file": "CCTV_lobby_aug19.mp4", "top_label": "firearm", "confidence": 0.783}',
        "ip_address": None,
    },
    {
        "id": _make_id(), "action": "CASE_STATUS_CHANGED",
        "case_id": CASE_ID,
        "metadata": '{"from": "OPEN", "to": "UNDER_REVIEW", "reason": "AI flagged firearm detection"}',
        "ip_address": "127.0.0.1",
    },
]


# ── Main seed function ────────────────────────────────────────────────────────
async def seed():
    config = _parse_db()
    pool = await aiomysql.create_pool(**config, minsize=1, maxsize=3)

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:

            # Check if case already exists
            await cur.execute("SELECT id FROM cases WHERE case_number = %s", (CASE_NUMBER,))
            existing = await cur.fetchone()
            if existing:
                print(f"[Seed] Case {CASE_NUMBER} already exists — skipping.")
                pool.close()
                await pool.wait_closed()
                return

            # Insert case
            await cur.execute(
                """INSERT INTO cases (id, case_number, title, description, status, created_by_name)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    CASE["id"], CASE["case_number"], CASE["title"],
                    CASE["description"], CASE["status"], CASE["created_by_name"],
                ),
            )
            print(f"[Seed] ✓ Case inserted: {CASE_NUMBER}")

            # Insert evidence
            for ev in EVIDENCE:
                await cur.execute(
                    """INSERT INTO evidence
                       (id, case_id, file_name, file_type, file_path, file_size,
                        mime_type, status, uploaded_at, processed_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        ev["id"], ev["case_id"], ev["file_name"], ev["file_type"],
                        ev["file_path"], ev["file_size"], ev["mime_type"],
                        ev["status"], ev["uploaded_at"], ev.get("processed_at"),
                    ),
                )
                print(f"[Seed]   ✓ Evidence: {ev['file_name']} ({ev['status']})")

            # Insert YOLOv8 detections
            for det in DETECTIONS:
                await cur.execute(
                    """INSERT INTO detections
                       (id, evidence_id, label, confidence, bounding_box,
                        frame_timestamp, grad_cam_path)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        det["id"], det["evidence_id"], det["label"],
                        det["confidence"], det["bounding_box"],
                        det["frame_timestamp"], det.get("grad_cam_path"),
                    ),
                )
                print(f"[Seed]   ✓ Detection: {det['label']} @ {det['confidence']*100:.1f}%")

            # Insert audit logs
            for log in AUDIT_LOGS:
                await cur.execute(
                    """INSERT INTO audit_logs (id, action, case_id, metadata, ip_address)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (log["id"], log["action"], log["case_id"], log["metadata"], log.get("ip_address")),
                )
            print(f"[Seed]   ✓ Audit logs: {len(AUDIT_LOGS)} entries")

            await conn.commit()

    pool.close()
    await pool.wait_closed()
    print(f"\n[Seed] ✅ Done! Case '{CASE_NUMBER}' is in the database.")
    print(f"[Seed]    Open the app and navigate to Cases → {CASE_NUMBER}")


if __name__ == "__main__":
    asyncio.run(seed())
