"""
backend/routes/evidence.py
──────────────────────────
Evidence ingestion routes.

Endpoints:
  POST   /api/evidence/upload    → Upload a file, attach to case, trigger background processing
  GET    /api/evidence/{id}      → Evidence detail (with detections)
  PATCH  /api/evidence/{id}/status → Update processing status (used by background tasks)
  DELETE /api/evidence/{id}      → Delete evidence + file from storage
"""

import uuid
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.database.db import get_db, write_audit_log

router = APIRouter()

# Allowed MIME types
ALLOWED_TYPES: dict[str, str] = {
    # Images
    "image/jpeg": "IMAGE",
    "image/png": "IMAGE",
    "image/webp": "IMAGE",
    # Videos
    "video/mp4": "VIDEO",
    "video/x-msvideo": "VIDEO",
    "video/quicktime": "VIDEO",
    # Audio
    "audio/mpeg": "AUDIO",
    "audio/wav": "AUDIO",
    "audio/ogg": "AUDIO",
    # Documents
    "application/pdf": "DOCUMENT",
}


# ── Background task stub ─────────────────────────────────────────────────────

async def _process_evidence(evidence_id: str, file_path: str, file_type: str, sio):
    """
    Placeholder background processing task.
    Phase 1: Will call YOLOv8 + Grad-CAM detector.
    Phase 2: Will call Whisper / OCR extractor.
    """
    db = await get_db()
    try:
        # Mark as PROCESSING
        await db.execute(
            "UPDATE evidence SET status = 'PROCESSING' WHERE id = ?", (evidence_id,)
        )
        await db.commit()

        # Emit Socket.io event to connected clients
        await sio.emit("evidence:status_update", {
            "evidence_id": evidence_id,
            "status": "PROCESSING",
            "progress": 0,
            "message": "Processing started...",
        })

        # TODO Phase 1: await run_yolov8_detection(evidence_id, file_path)
        # TODO Phase 2: await run_extraction(evidence_id, file_path, file_type)

        # Simulate completion (remove when real processing is added)
        await db.execute(
            "UPDATE evidence SET status = 'PENDING', processed_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), evidence_id),
        )
        await db.commit()

        await sio.emit("evidence:status_update", {
            "evidence_id": evidence_id,
            "status": "PENDING",
            "progress": 100,
            "message": "Awaiting AI analysis (Phase 1).",
        })
    except Exception as e:
        await db.execute(
            "UPDATE evidence SET status = 'FAILED' WHERE id = ?", (evidence_id,)
        )
        await db.commit()
        await sio.emit("evidence:status_update", {
            "evidence_id": evidence_id,
            "status": "FAILED",
            "message": str(e),
        })
    finally:
        await db.close()


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/upload", status_code=201)
async def upload_evidence(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    case_id: str = Form(...),
    disclaimer_accepted: bool = Form(...),   # Hold Point enforcement
):
    # Enforce the Hold Point disclaimer
    if not disclaimer_accepted:
        raise HTTPException(
            status_code=422,
            detail="You must accept the evidence upload disclaimer before proceeding.",
        )

    # Validate MIME type
    mime = file.content_type or ""
    file_type = ALLOWED_TYPES.get(mime)
    if not file_type:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {mime}. Allowed: {list(ALLOWED_TYPES.keys())}",
        )

    # Verify case exists
    db = await get_db()
    try:
        row = await db.execute("SELECT id FROM cases WHERE id = ?", (case_id,))
        if not await row.fetchone():
            raise HTTPException(status_code=404, detail="Case not found")
    finally:
        await db.close()

    # Save file to storage
    evidence_id = uuid.uuid4().hex
    storage_dir = Path(settings.STORAGE_DIR) / case_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{evidence_id}_{file.filename}"
    dest_path = storage_dir / safe_name

    with dest_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    file_size = dest_path.stat().st_size

    # Insert DB record
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO evidence
               (id, case_id, file_name, file_type, file_path, file_size, mime_type, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING')""",
            (
                evidence_id,
                case_id,
                file.filename,
                file_type,
                str(dest_path),
                file_size,
                mime,
            ),
        )
        await db.commit()
        row = await db.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,))
        evidence = dict(await row.fetchone())
    finally:
        await db.close()

    await write_audit_log(
        action="UPLOAD_EVIDENCE",
        case_id=case_id,
        metadata={"evidence_id": evidence_id, "file_name": file.filename, "file_type": file_type},
        ip_address=request.client.host if request.client else None,
    )

    # Import sio lazily to avoid circular import
    from backend.main import sio
    background_tasks.add_task(_process_evidence, evidence_id, str(dest_path), file_type, sio)

    return evidence


@router.get("/{evidence_id}")
async def get_evidence(evidence_id: str):
    db = await get_db()
    try:
        row = await db.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,))
        ev = dict(await row.fetchone() or {})
        if not ev:
            raise HTTPException(status_code=404, detail="Evidence not found")

        det_cursor = await db.execute(
            "SELECT * FROM detections WHERE evidence_id = ? ORDER BY created_at",
            (evidence_id,),
        )
        ev["detections"] = [dict(r) for r in await det_cursor.fetchall()]
    finally:
        await db.close()

    return ev


@router.delete("/{evidence_id}", status_code=204)
async def delete_evidence(evidence_id: str, request: Request):
    db = await get_db()
    try:
        row = await db.execute(
            "SELECT file_path, case_id FROM evidence WHERE id = ?", (evidence_id,)
        )
        ev = dict(await row.fetchone() or {})
        if not ev:
            raise HTTPException(status_code=404, detail="Evidence not found")

        # Remove file from disk
        file_path = Path(ev["file_path"])
        if file_path.exists():
            file_path.unlink()

        await db.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))
        await db.commit()
    finally:
        await db.close()

    await write_audit_log(
        action="DELETE_EVIDENCE",
        case_id=ev.get("case_id"),
        metadata={"evidence_id": evidence_id},
        ip_address=request.client.host if request.client else None,
    )
