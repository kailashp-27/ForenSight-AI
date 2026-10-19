"""
backend/routes/forensic.py
──────────────────────────
Operator workbench API (mounted at /api/v1).

  POST   /api/v1/scan-roi                    ROI → crop → local VLM → unverified draft
  GET    /api/v1/video/{evidence_id}/meta    fps / frame count / dimensions / SHA-256
  GET    /api/v1/evidence/{id}/findings      all ROI findings for a clip
  POST   /api/v1/findings/{id}/verify        human approval (drafts → Verified)
  PATCH  /api/v1/findings/{id}               operator correction (resets verification)
  GET    /api/v1/cases/{case_id}/graph       entity graph (verified findings only)
  GET    /api/v1/cases/{case_id}/timeline    multi-track timeline data
  GET    /api/v1/audit                       chain-of-custody entries
  GET    /api/v1/audit/verify                recompute and verify the hash chain
  GET    /api/v1/audit/{seq}/payload         decrypt the stored raw model payload

Legal posture: findings are ASSISTIVE observations. They are created as
"Unverified_Draft" and only an explicit operator action verifies them; any
substantive edit to a verified finding resets it to draft.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from backend.database.db import get_db
from backend.modules import audit_engine
from backend.modules.graph_engine import get_case_graph
from backend.modules.vision import cv_engine
from backend.modules.vision.objective_lexicon import enforce_many, enforce_objective_lexicon
from backend.modules.vision.vlm_client import VLMClient, VLMOutputError, VLMUnavailableError
from backend.schemas import (
    Finding, FindingEdit, ScanResponse, VerifyRequest, VLMScanRequest, VideoMeta,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# One VLM inference at a time: a 7B vision model shares the GPU/RAM with
# Whisper and the rest of the stack, and concurrent runs just thrash.
_VLM_LOCK = asyncio.Semaphore(1)


# ── helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _get_video_evidence(evidence_id: str) -> Dict[str, Any]:
    """Load a VIDEO evidence row, make sure its file exists and has a stored SHA-256."""
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM evidence WHERE id = %s", (evidence_id,))
        row = await cur.fetchone()
        await db.commit()
    finally:
        await db.close()

    if not row:
        raise HTTPException(status_code=404, detail="Evidence not found")
    ev = dict(row)
    if ev["file_type"] != "VIDEO":
        raise HTTPException(status_code=400, detail="ROI inspection is only available for VIDEO evidence")
    if not Path(ev["file_path"]).is_file():
        raise HTTPException(status_code=404, detail="Evidence file is missing from storage")

    # Evidence uploaded before hashing existed: hash once, persist, log it.
    if not ev.get("file_hash_sha256"):
        digest = await run_in_threadpool(cv_engine.sha256_file, ev["file_path"])
        db = await get_db()
        try:
            await db.execute(
                "UPDATE evidence SET file_hash_sha256 = %s WHERE id = %s", (digest, evidence_id)
            )
            await db.commit()
        finally:
            await db.close()
        ev["file_hash_sha256"] = digest
        await audit_engine.append_entry(
            "EVIDENCE_HASH_RECORDED", case_id=ev["case_id"], evidence_id=evidence_id,
            file_hash_sha256=digest, metadata={"note": "SHA-256 computed on first forensic access"},
        )
    return ev


def _row_to_finding(row: Dict[str, Any]) -> Finding:
    try:
        roi = json.loads(row.get("bounding_box") or "[]")
    except json.JSONDecodeError:
        roi = []
    try:
        details = json.loads(row.get("details_json") or "[]")
    except json.JSONDecodeError:
        details = []
    ts_ms = int(round(float(row.get("frame_timestamp") or 0.0) * 1000))
    created = row.get("created_at")
    return Finding(
        id=row["id"],
        evidence_id=row["evidence_id"],
        label=row["label"],
        category=row.get("category") or "OBJECT",
        readout_text=row.get("readout_text") or "NONE",
        details=details,
        objective_lexicon_compliant=bool(row.get("lexicon_compliant", 1)),
        confidence_score=float(row["confidence"]),
        frame_index=int(row.get("frame_index") or 0),
        timestamp_ms=ts_ms,
        timestamp_str=row.get("timestamp_str") or cv_engine.format_timestamp(ts_ms),
        roi_px=[int(v) for v in roi],
        frame_sha256=row.get("frame_sha256") or "",
        crop_sha256=row.get("crop_sha256") or "",
        operator_id=row.get("operator_id") or "UNKNOWN",
        verification_status=row.get("verification_status") or "Unverified_Draft",
        verified_by=row.get("verified_by"),
        verified_at=row.get("verified_at"),
        role=row.get("role"),
        subject_name=row.get("subject_name"),
        source_reference=(
            f"evidence:{row['evidence_id']} frame:{row.get('frame_index')} "
            f"t={row.get('timestamp_str')} roi={roi}"
        ),
        created_at=str(created) if created else None,
    )


async def _load_finding_row(finding_id: str) -> Dict[str, Any]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT d.*, e.case_id, e.file_hash_sha256 AS evidence_hash
               FROM detections d JOIN evidence e ON e.id = d.evidence_id
               WHERE d.id = %s AND d.source = 'VLM_ROI'""",
            (finding_id,),
        )
        row = await cur.fetchone()
        await db.commit()
    finally:
        await db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Finding not found")
    return dict(row)


# ── scan ─────────────────────────────────────────────────────────────────────

@router.post("/scan-roi", response_model=ScanResponse, status_code=201)
async def scan_roi(body: VLMScanRequest, request: Request) -> ScanResponse:
    ev = await _get_video_evidence(body.video_id)

    # 1-2. Exact frame + ROI patch (CPU-bound → threadpool)
    def _prepare():
        frame, info, probe = cv_engine.extract_frame(
            ev["file_path"], frame_index=body.frame_offset, timestamp_ms=body.timestamp_ms
        )
        h, w = frame.shape[:2]
        roi_px = cv_engine.relative_to_pixels(body.x1, body.y1, body.x2, body.y2, w, h)
        return info, cv_engine.prepare_roi_patch(frame, roi_px)

    try:
        info, patch = await run_in_threadpool(_prepare)
    except cv_engine.VideoError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # 3. Local VLM (schema-constrained, air-gapped)
    try:
        client = VLMClient()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    try:
        async with _VLM_LOCK:
            call = await client.analyze_patch(patch.patch_b64)
    except VLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except VLMOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    result = call.result

    # 4. Chain of custody: encrypted raw payload + hashes of exactly what was analysed
    encrypted = audit_engine.encrypt_payload(
        call.raw_response, aad=f"{ev['id']}:{patch.frame_sha256}"
    )
    audit = await audit_engine.append_entry(
        "VLM_ROI_SCAN",
        operator_id=body.operator_id,
        case_id=ev["case_id"],
        evidence_id=ev["id"],
        file_hash_sha256=ev["file_hash_sha256"],
        metadata={
            "frame_index": info.index,
            "timestamp": info.timestamp_str,
            "roi_px": patch.roi_px,
            "crop_box_px": patch.crop_box_px,
            "frame_sha256": patch.frame_sha256,
            "crop_sha256": patch.crop_sha256,
            "model": call.model,
            "latency_ms": call.latency_ms,
            "lexicon_compliant": result.objective_lexicon_compliant,
            "raw_vlm_response": encrypted,
        },
    )

    # 5. Persist as an UNVERIFIED DRAFT
    finding_id = uuid.uuid4().hex
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO detections
               (id, evidence_id, label, confidence, bounding_box, frame_timestamp,
                source, category, readout_text, details_json, lexicon_compliant,
                frame_index, timestamp_str, frame_sha256, crop_sha256, operator_id,
                verification_status, audit_seq)
               VALUES (%s,%s,%s,%s,%s,%s,'VLM_ROI',%s,%s,%s,%s,%s,%s,%s,%s,%s,'Unverified_Draft',%s)""",
            (
                finding_id, ev["id"], result.label, result.confidence_score,
                json.dumps(patch.roi_px), info.timestamp_ms / 1000.0,
                result.category, result.readout_text, json.dumps(result.details),
                1 if result.objective_lexicon_compliant else 0,
                info.index, info.timestamp_str, patch.frame_sha256, patch.crop_sha256,
                body.operator_id, audit["seq"],
            ),
        )
        await db.commit()
    except Exception:
        await db.conn.rollback()
        raise
    finally:
        await db.close()

    row = await _load_finding_row(finding_id)
    return ScanResponse(
        finding=_row_to_finding(row),
        crop_preview_b64=patch.patch_b64,
        vlm_latency_ms=call.latency_ms,
    )


# ── video meta / findings ────────────────────────────────────────────────────

@router.get("/findings/{finding_id}/crop")
async def finding_crop(finding_id: str):
    """JPEG of the region an investigator marked (10 percent context) — the 'photo' of a finding."""
    import cv2
    from fastapi.responses import Response

    row = await _load_finding_row(finding_id)
    ev = await _get_video_evidence(row["evidence_id"])
    try:
        x1, y1, x2, y2 = (int(v) for v in json.loads(row.get("bounding_box") or "[]"))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Finding has no usable region")

    def _render() -> bytes:
        frame, _info, _probe = cv_engine.extract_frame(ev["file_path"], frame_index=int(row.get("frame_index") or 0))
        h, w = frame.shape[:2]
        px, py = int((x2 - x1) * 0.1), int((y2 - y1) * 0.1)
        crop = frame[max(0, y1 - py): min(h, y2 + py), max(0, x1 - px): min(w, x2 + px)]
        if crop.size == 0:
            raise cv_engine.VideoError("Empty crop")
        if max(crop.shape[:2]) < 160:
            s = 160 / max(crop.shape[:2])
            crop = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
        ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return buf.tobytes()

    try:
        data = await run_in_threadpool(_render)
    except (cv_engine.VideoError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


@router.get("/video/{evidence_id}/meta", response_model=VideoMeta)
async def video_meta(evidence_id: str) -> VideoMeta:
    ev = await _get_video_evidence(evidence_id)
    try:
        probe = await run_in_threadpool(cv_engine.probe_video, ev["file_path"])
    except cv_engine.VideoError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return VideoMeta(
        evidence_id=evidence_id, fps=probe.fps, frame_count=probe.frame_count,
        width=probe.width, height=probe.height, duration_ms=probe.duration_ms,
        file_sha256=ev["file_hash_sha256"],
    )


@router.get("/evidence/{evidence_id}/findings", response_model=List[Finding])
async def list_findings(evidence_id: str) -> List[Finding]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT * FROM detections
               WHERE evidence_id = %s AND source = 'VLM_ROI'
               ORDER BY frame_timestamp, created_at""",
            (evidence_id,),
        )
        rows = [dict(r) for r in await cur.fetchall()]
        await db.commit()
    finally:
        await db.close()
    return [_row_to_finding(r) for r in rows]


# ── human-in-the-loop ────────────────────────────────────────────────────────

@router.post("/findings/{finding_id}/verify", response_model=Finding)
async def verify_finding(finding_id: str, body: VerifyRequest) -> Finding:
    row = await _load_finding_row(finding_id)
    if row["verification_status"] == "Verified":
        return _row_to_finding(row)

    verified_at = _now_iso()
    db = await get_db()
    try:
        await db.execute(
            """UPDATE detections
               SET verification_status = 'Verified', verified_by = %s, verified_at = %s,
                   role = COALESCE(%s, role), subject_name = COALESCE(%s, subject_name)
               WHERE id = %s""",
            (body.operator_id, verified_at, body.role, body.subject_name, finding_id),
        )
        await db.commit()
    finally:
        await db.close()

    await audit_engine.append_entry(
        "FINDING_VERIFIED", operator_id=body.operator_id, case_id=row["case_id"],
        evidence_id=row["evidence_id"], file_hash_sha256=row.get("evidence_hash"),
        metadata={"finding_id": finding_id, "crop_sha256": row.get("crop_sha256"),
                  "label": row["label"], "role": body.role, "subject_name": body.subject_name},
    )
    return _row_to_finding(await _load_finding_row(finding_id))


@router.post("/findings/{finding_id}/unverify", response_model=Finding)
async def unverify_finding(finding_id: str, body: VerifyRequest) -> Finding:
    """Revoke a verification (investigator changed their mind / found an error)."""
    row = await _load_finding_row(finding_id)
    if row["verification_status"] != "Verified":
        return _row_to_finding(row)

    db = await get_db()
    try:
        await db.execute(
            """UPDATE detections
               SET verification_status = 'Unverified_Draft', verified_by = NULL, verified_at = NULL
               WHERE id = %s""",
            (finding_id,),
        )
        await db.commit()
    finally:
        await db.close()

    await audit_engine.append_entry(
        "FINDING_VERIFICATION_REVOKED", operator_id=body.operator_id, case_id=row["case_id"],
        evidence_id=row["evidence_id"], file_hash_sha256=row.get("evidence_hash"),
        metadata={"finding_id": finding_id, "previously_verified_by": row.get("verified_by")},
    )
    return _row_to_finding(await _load_finding_row(finding_id))


@router.patch("/findings/{finding_id}", response_model=Finding)
async def edit_finding(finding_id: str, body: FindingEdit) -> Finding:
    row = await _load_finding_row(finding_id)

    changes: Dict[str, Any] = {}
    compliant = bool(row.get("lexicon_compliant", 1))
    if body.label is not None:
        text, ok = enforce_objective_lexicon(body.label)
        changes["label"] = text
        compliant = compliant and ok
    if body.readout_text is not None:
        text, ok = enforce_objective_lexicon(body.readout_text)
        changes["readout_text"] = text
        compliant = compliant and ok
    if body.details is not None:
        texts, ok = enforce_many(body.details)
        changes["details_json"] = json.dumps(texts[:3])
        compliant = compliant and ok
    if body.role is not None:
        changes["role"] = body.role
    if body.subject_name is not None:
        changes["subject_name"] = body.subject_name
    if not changes:
        raise HTTPException(status_code=422, detail="No editable fields supplied")

    sets = ", ".join(f"{k} = %s" for k in changes)
    # Any substantive edit invalidates a prior human verification.
    db = await get_db()
    try:
        await db.execute(
            f"""UPDATE detections SET {sets},
                    verification_status = 'Unverified_Draft',
                    verified_by = NULL, verified_at = NULL
                WHERE id = %s""",
            (*changes.values(), finding_id),
        )
        await db.commit()
    finally:
        await db.close()

    await audit_engine.append_entry(
        "FINDING_EDITED", operator_id=body.operator_id, case_id=row["case_id"],
        evidence_id=row["evidence_id"], file_hash_sha256=row.get("evidence_hash"),
        metadata={
            "finding_id": finding_id,
            "was_verified": row["verification_status"] == "Verified",
            "changed_fields": sorted(changes.keys()),
        },
    )
    return _row_to_finding(await _load_finding_row(finding_id))


# ── case views ───────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/graph")
async def case_graph(case_id: str) -> Dict[str, Any]:
    return await get_case_graph(case_id)


@router.get("/cases/{case_id}/timeline")
async def case_timeline(
    case_id: str,
    include_drafts: bool = Query(False, description="Also include unverified drafts"),
) -> Dict[str, Any]:
    """
    Multi-track timeline: one track per evidence clip. Times are offsets (ms)
    from the start of each clip — CCTV clips have no shared absolute clock.
    """
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT id, file_name, file_type FROM evidence WHERE case_id = %s ORDER BY uploaded_at",
            (case_id,),
        )
        evidence = [dict(r) for r in await cur.fetchall()]

        status_clause = "" if include_drafts else "AND d.verification_status = 'Verified'"
        cur = await db.execute(
            f"""SELECT d.id, d.evidence_id, d.label, d.category, d.confidence,
                       d.frame_timestamp, d.timestamp_str, d.verification_status,
                       d.readout_text
                FROM detections d JOIN evidence e ON e.id = d.evidence_id
                WHERE e.case_id = %s AND d.source = 'VLM_ROI' {status_clause}
                ORDER BY d.frame_timestamp""",
            (case_id,),
        )
        findings = [dict(r) for r in await cur.fetchall()]

        cur = await db.execute(
            """SELECT t.id, t.evidence_id, t.content, t.start_time, t.end_time
               FROM text_chunks t JOIN evidence e ON e.id = t.evidence_id
               WHERE e.case_id = %s AND t.start_time IS NOT NULL
               ORDER BY t.start_time""",
            (case_id,),
        )
        chunks = [dict(r) for r in await cur.fetchall()]
        await db.commit()
    finally:
        await db.close()

    items: List[Dict[str, Any]] = []
    for f in findings:
        start_ms = int(round(float(f["frame_timestamp"] or 0.0) * 1000))
        items.append({
            "id": f"finding:{f['id']}", "track": f["evidence_id"], "kind": "finding",
            "start_ms": start_ms, "end_ms": None,
            "label": f["label"], "category": f["category"],
            "confidence": float(f["confidence"]),
            "verified": f["verification_status"] == "Verified",
            "text": f.get("readout_text"), "timestamp_str": f["timestamp_str"],
        })
    for c in chunks:
        start_ms = int(round(float(c["start_time"]) * 1000))
        end_ms = int(round(float(c["end_time"]) * 1000)) if c["end_time"] is not None else None
        items.append({
            "id": f"chunk:{c['id']}", "track": c["evidence_id"], "kind": "transcript",
            "start_ms": start_ms, "end_ms": end_ms,
            "label": (c["content"] or "")[:60], "category": None, "confidence": None,
            "verified": False, "text": c["content"],
            "timestamp_str": cv_engine.format_timestamp(start_ms),
        })

    return {
        "tracks": [{"id": e["id"], "name": e["file_name"], "file_type": e["file_type"]} for e in evidence],
        "items": items,
    }


# ── chain of custody ─────────────────────────────────────────────────────────

@router.get("/audit")
async def audit_list(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    case_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    rows = await audit_engine.list_entries(limit, offset, case_id, evidence_id)
    for r in rows:
        try:
            r["metadata_json"] = json.loads(r["metadata_json"])
        except (TypeError, json.JSONDecodeError):
            pass
        # Never expose ciphertext in list views; use the dedicated decrypt route.
        meta = r["metadata_json"]
        if isinstance(meta, dict) and "raw_vlm_response" in meta:
            meta["raw_vlm_response"] = "[encrypted — see /audit/{seq}/payload]"
    return rows


@router.get("/audit/verify")
async def audit_verify() -> Dict[str, Any]:
    report = await audit_engine.verify_chain()
    return {
        "ok": report.ok,
        "entries_checked": report.entries_checked,
        "head_seq": report.head_seq,
        "head_hash": report.head_hash,
        "broken_at_seq": report.broken_at_seq,
        "reason": report.reason,
    }


@router.get("/audit/{seq}/payload")
async def audit_payload(seq: int, request: Request) -> Dict[str, Any]:
    entry = await audit_engine.get_entry(seq)
    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    try:
        meta = json.loads(entry["metadata_json"])
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Corrupt audit metadata")
    blob = meta.get("raw_vlm_response") if isinstance(meta, dict) else None
    if not isinstance(blob, dict):
        raise HTTPException(status_code=404, detail="Entry has no encrypted payload")
    try:
        plaintext = audit_engine.decrypt_payload(blob)
    except Exception:
        raise HTTPException(status_code=409, detail="Payload could not be decrypted (wrong key or tampered)")

    # Reading raw model output is itself an auditable act.
    await audit_engine.append_entry(
        "AUDIT_PAYLOAD_VIEWED", operator_id="OPERATOR",
        case_id=entry["case_id"], evidence_id=entry["evidence_id"],
        metadata={"viewed_seq": seq, "ip_address": request.client.host if request.client else None},
    )
    return {"seq": seq, "raw_vlm_response": plaintext}
