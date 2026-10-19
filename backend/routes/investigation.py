"""
backend/routes/investigation.py
───────────────────────────────
Case-level automatic analysis, correlation, map, graph and report (/api/v1).

  POST /cases/{id}/analyze          run automatic analysis on all evidence (background)
  POST /evidence/{id}/analyze       run it on one evidence item
  GET  /cases/{id}/analysis-status  per-evidence status + live progress
  GET  /cases/{id}/clues            every extracted clue (with cross-evidence match ids)
  GET  /cases/{id}/correlations     cross-evidence matches, strongest first
  GET  /cases/{id}/clue-graph       evidence ↔ matched-clue graph (Cytoscape)
  GET  /cases/{id}/map              located evidence + match links
  PUT  /evidence/{id}/location      set / correct a location manually
  GET  /evidence/{id}/clues         clues of one file, flagged when matched elsewhere
  GET  /cases/{id}/report           HTML report (add ?download=true for attachment)
  GET  /capabilities                which analysers are available
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response
from typing import Literal

import cv2
from pydantic import BaseModel, Field

from backend.database.db import get_db
from backend.modules import audit_engine, auto_analysis, investigation_service as svc
from backend.modules.report_engine import build_report_html
from backend.modules.clue_terms import object_key
from backend.modules.case_summary import build_key_findings
from backend.modules.event_timeline import build_event_timeline
from backend.modules.clue_text import match_key
from backend.modules.vision import cv_engine
from backend.modules.vision.objective_lexicon import enforce_objective_lexicon

router = APIRouter()


class LocationBody(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    label: Optional[str] = Field(default=None, max_length=255)
    operator_id: str = Field(default="OPERATOR", min_length=1, max_length=100)


class ReviewBody(BaseModel):
    decision: Literal["confirm", "reject", "relabel"]
    class_name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    operator_id: str = Field(default="OPERATOR", min_length=1, max_length=100)


async def _require_case(case_id: str) -> Dict[str, Any]:
    data = await svc.case_correlations(case_id)
    if not data:
        raise HTTPException(status_code=404, detail="Case not found")
    return data


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    return await run_in_threadpool(auto_analysis.capabilities)


# ── analysis ─────────────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/analyze", status_code=202)
async def analyze_case(case_id: str, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    ctx = await svc.load_case_context(case_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Case not found")
    if not ctx["evidence"]:
        raise HTTPException(status_code=400, detail="Case has no evidence to analyse")
    background_tasks.add_task(svc.analyze_case, case_id)
    return {"status": "started", "evidence_count": len(ctx["evidence"])}


@router.post("/evidence/{evidence_id}/analyze", status_code=202)
async def analyze_one(evidence_id: str, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT id FROM evidence WHERE id=%s", (evidence_id,))
        row = await cur.fetchone()
        await db.commit()
    finally:
        await db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Evidence not found")
    background_tasks.add_task(svc.analyze_evidence, evidence_id)
    return {"status": "started"}


@router.get("/cases/{case_id}/analysis-status")
async def analysis_status(case_id: str) -> Dict[str, Any]:
    ctx = await svc.load_case_context(case_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Case not found")
    items = []
    for e in ctx["evidence"]:
        live = svc.get_progress(e["id"]) or {}
        items.append({
            "evidence_id": e["id"], "file_name": e["file_name"], "file_type": e["file_type"],
            "status": live.get("status") or e.get("analysis_status") or "NOT_RUN",
            "progress": live.get("progress", e.get("analysis_progress") or 0),
            "message": e.get("analysis_message"),
        })
    running = any(i["status"] == "RUNNING" for i in items)
    return {"running": running, "items": items}


# ── read models ──────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/correlations")
async def correlations(case_id: str, include_weak: bool = True) -> Dict[str, Any]:
    data = await _require_case(case_id)
    matches = [m for m in data["matches"] if include_weak or m["strength"] != "WEAK"]
    return {
        "matches": matches,
        "totals": {
            "clues": len(data["clues"]),
            "matches": len(data["matches"]),
            "strong": sum(m["strength"] == "STRONG" for m in data["matches"]),
            "medium": sum(m["strength"] == "MEDIUM" for m in data["matches"]),
            "weak": sum(m["strength"] == "WEAK" and m["kind"] != "KEYWORD" for m in data["matches"]),
            "keywords": sum(m["kind"] == "KEYWORD" for m in data["matches"]),
            "evidence": len(data["evidence"]),
        },
    }


@router.get("/cases/{case_id}/clues")
async def case_clues(case_id: str) -> List[Dict[str, Any]]:
    data = await _require_case(case_id)
    matched: Dict[str, List[str]] = {}
    for m in data["matches"]:
        for mem in m["members"]:
            matched.setdefault(mem["clue_id"], []).append(m["id"])
    names = {k: v["file_name"] for k, v in data["evidence"].items()}
    out = []
    for c in data["clues"]:
        out.append({**c, "file_name": names.get(c["evidence_id"]), "match_ids": matched.get(c["id"], [])})
    return out


@router.get("/evidence/{evidence_id}/clues")
async def evidence_clues(evidence_id: str) -> Dict[str, Any]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT case_id FROM evidence WHERE id=%s", (evidence_id,))
        row = await cur.fetchone()
        await db.commit()
    finally:
        await db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Evidence not found")
    data = await _require_case(row["case_id"])

    by_clue: Dict[str, List[Dict[str, Any]]] = {}
    for m in data["matches"]:
        for mem in m["members"]:
            if mem["evidence_id"] == evidence_id:
                by_clue.setdefault(mem["clue_id"], []).append({
                    "match_id": m["id"], "strength": m["strength"], "match_type": m["match_type"],
                    "score": m["score"], "explanation": m["explanation"],
                    "also_in": [x for x in m["members"] if x["evidence_id"] != evidence_id],
                })
    clues = []
    for c in data["clues"]:
        if c["evidence_id"] != evidence_id:
            continue
        clues.append({**c, "matches": by_clue.get(c["id"], [])})
    clues.sort(key=lambda c: (-len(c["matches"]), -(c["confidence"] or 0)))
    return {"clues": clues, "matched_count": sum(1 for c in clues if c["matches"])}


@router.get("/cases/{case_id}/clue-graph")
async def clue_graph(case_id: str, include_weak: bool = False) -> Dict[str, Any]:
    data = await _require_case(case_id)
    return svc.build_clue_graph(data["matches"], data["evidence"], include_weak)


@router.get("/cases/{case_id}/map")
async def case_map(case_id: str) -> Dict[str, Any]:
    data = await _require_case(case_id)
    return svc.build_map(data["ctx"], data["matches"])


@router.put("/evidence/{evidence_id}/location")
async def set_location(evidence_id: str, body: LocationBody, request: Request) -> Dict[str, Any]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT case_id, file_hash_sha256 FROM evidence WHERE id=%s", (evidence_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Evidence not found")
        await db.execute(
            "UPDATE evidence SET latitude=%s, longitude=%s, location_label=%s WHERE id=%s",
            (body.latitude, body.longitude, body.label or "Manual entry", evidence_id))
        await db.commit()
    finally:
        await db.close()
    await audit_engine.append_entry(
        "EVIDENCE_LOCATION_SET", operator_id=body.operator_id, case_id=row["case_id"],
        evidence_id=evidence_id, file_hash_sha256=row.get("file_hash_sha256"),
        metadata={"latitude": body.latitude, "longitude": body.longitude, "label": body.label})
    return {"evidence_id": evidence_id, "latitude": body.latitude, "longitude": body.longitude}


# ── report ───────────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/report", response_class=HTMLResponse)
async def report(case_id: str, download: bool = Query(False), request: Request = None) -> HTMLResponse:
    data = await _require_case(case_id)
    ctx = data["ctx"]

    findings, auto = [], []
    from backend.routes.forensic import _row_to_finding  # reuse the finding mapper
    for d in ctx["detections"]:
        if d.get("source") == "VLM_ROI":
            findings.append(_row_to_finding(d).model_dump() | {"confidence": d["confidence"]})
        elif d.get("source") == "AUTO_YOLO" and d.get("verification_status") != "Rejected":
            auto.append({"evidence_id": d["evidence_id"], "label": d["label"],
                         "timestamp_str": d.get("timestamp_str"), "confidence": d["confidence"]})

    chain = await audit_engine.verify_chain()
    from backend.modules.people_roster import build_roster
    people = build_roster(ctx, data["clues"], data["matches"], ctx.get("designations", []))
    _db = await get_db()
    try:
        _cur = await _db.execute(
            """SELECT l.person_key, l.decided_by, c.id AS cid, c.full_name FROM citizen_links l
               JOIN citizens c ON c.id = l.citizen_id WHERE l.case_id=%s AND l.status='CONFIRMED'""", (case_id,))
        confirmed = {r["person_key"]: r for r in await _cur.fetchall()}
        await _db.commit()
    finally:
        await _db.close()
    for p in people:
        link = confirmed.get(p["key"])
        p["citizen"] = (f"Citizen register #{link['cid']} {link['full_name']} (confirmed by {link['decided_by']})"
                        if link else None)
    html_doc = build_report_html({
        "people": people,
        "case": ctx["case"], "evidence": ctx["evidence"], "matches": data["matches"],
        "findings": findings, "auto_detections": auto,
        "chain": {"ok": chain.ok, "entries_checked": chain.entries_checked,
                  "broken_at_seq": chain.broken_at_seq, "reason": chain.reason,
                  "head_hash": chain.head_hash},
        "capabilities": {"detector_model": auto_analysis.capabilities()["detector_model"]},
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    })

    await audit_engine.append_entry(
        "REPORT_GENERATED", operator_id="OPERATOR", case_id=case_id,
        metadata={"report_sha256": hashlib.sha256(html_doc.encode("utf-8")).hexdigest(),
                  "matches": len(data["matches"]), "evidence": len(ctx["evidence"]),
                  "ip_address": request.client.host if request and request.client else None})

    headers = {}
    if download:
        num = (ctx["case"].get("case_number") or case_id).replace("/", "-")
        headers["Content-Disposition"] = f'attachment; filename="ForenSight_Report_{num}.html"'
    return HTMLResponse(content=html_doc, headers=headers)


# ── detection review (human-in-the-loop feedback; feeds fine-tuning) ──────────

@router.get("/evidence/{evidence_id}/detections")
async def list_detections(evidence_id: str, include_rejected: bool = False) -> List[Dict[str, Any]]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT id, label, class_name, category, confidence, bounding_box, frame_index,
                      timestamp_str, frame_timestamp, readout_text, verification_status,
                      verified_by, track_key
               FROM detections WHERE evidence_id=%s AND source='AUTO_YOLO'
               ORDER BY frame_timestamp, id""", (evidence_id,))
        rows = [dict(r) for r in await cur.fetchall()]
        await db.commit()
    finally:
        await db.close()
    out = []
    for r in rows:
        if r["verification_status"] == "Rejected" and not include_rejected:
            continue
        try:
            r["bounding_box"] = json.loads(r["bounding_box"])
        except (TypeError, json.JSONDecodeError):
            pass
        out.append(r)
    return out


@router.get("/detections/{detection_id}/crop")
async def detection_crop(detection_id: str) -> Response:
    """JPEG crop of the detected object (10 percent context) for the review UI."""
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT d.bounding_box, d.frame_index, e.file_path, e.file_type
               FROM detections d JOIN evidence e ON e.id=d.evidence_id WHERE d.id=%s""",
            (detection_id,))
        row = await cur.fetchone()
        await db.commit()
    finally:
        await db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Detection not found")
    try:
        box = json.loads(row["bounding_box"])
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=422, detail="Detection has no usable box")

    def _render() -> bytes:
        if row["file_type"] == "IMAGE":
            frame = cv2.imread(row["file_path"])
            if frame is None:
                raise cv_engine.VideoError("Could not decode image")
        else:
            frame, _info, _probe = cv_engine.extract_frame(
                row["file_path"], frame_index=int(row["frame_index"] or 0))
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = (float(v) for v in box)
        px, py = (x2 - x1) * 0.1, (y2 - y1) * 0.1
        crop = frame[max(0, int((y1 - py) * h)): int((y2 + py) * h),
                     max(0, int((x1 - px) * w)): int((x2 + px) * w)]
        if crop.size == 0:
            raise cv_engine.VideoError("Empty crop")
        if max(crop.shape[:2]) < 120:
            scale = 120 / max(crop.shape[:2])
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
        return buf.tobytes()

    try:
        data = await run_in_threadpool(_render)
    except (cv_engine.VideoError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


@router.post("/detections/{detection_id}/review")
async def review_detection(detection_id: str, body: ReviewBody) -> Dict[str, Any]:
    """Confirm, reject or relabel an automatic detection. Rejected ones leave the clue set."""
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT d.*, e.case_id, e.file_hash_sha256 AS ev_hash
               FROM detections d JOIN evidence e ON e.id=d.evidence_id
               WHERE d.id=%s AND d.source='AUTO_YOLO'""", (detection_id,))
        d = await cur.fetchone()
        if not d:
            raise HTTPException(status_code=404, detail="Automatic detection not found")
        d = dict(d)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if body.decision == "reject":
            await db.execute(
                "UPDATE detections SET verification_status='Rejected', verified_by=%s, verified_at=%s WHERE id=%s",
                (body.operator_id, now, detection_id))
            await db.execute("DELETE FROM clues WHERE id=%s", (detection_id,))
            result_label = d["label"]
        else:
            label = d["label"]
            if body.decision == "relabel":
                if not body.class_name:
                    raise HTTPException(status_code=422, detail="class_name is required to relabel")
                new_class = body.class_name.strip().lower()
                label, _ = enforce_objective_lexicon(auto_analysis.objective_class_label(new_class))
                await db.execute(
                    "UPDATE detections SET class_name=%s, label=%s, category=%s WHERE id=%s",
                    (new_class, label, auto_analysis.category_for(new_class), detection_id))
                await db.execute(
                    "UPDATE clues SET value=%s, norm_value=%s WHERE id=%s",
                    (label, label.lower(), detection_id))
            await db.execute(
                "UPDATE detections SET verification_status='Verified', verified_by=%s, verified_at=%s WHERE id=%s",
                (body.operator_id, now, detection_id))
            result_label = label
        await db.commit()
    except HTTPException:
        raise
    finally:
        await db.close()

    await audit_engine.append_entry(
        "DETECTION_REVIEWED", operator_id=body.operator_id, case_id=d["case_id"],
        evidence_id=d["evidence_id"], file_hash_sha256=d.get("ev_hash"),
        metadata={"detection_id": detection_id, "decision": body.decision,
                  "previous_label": d["label"], "new_label": result_label,
                  "class_name": body.class_name})
    return {"id": detection_id, "decision": body.decision, "label": result_label}


@router.get("/cases/{case_id}/review-queue")
async def review_queue(case_id: str, limit: int = Query(60, ge=1, le=300)) -> Dict[str, Any]:
    """Unreviewed automatic detections, lowest confidence first (a human label
    is worth most where the model is least sure)."""
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT d.id, d.evidence_id, e.file_name, d.label, d.class_name, d.confidence,
                      d.timestamp_str, d.readout_text, d.verification_status
               FROM detections d JOIN evidence e ON e.id=d.evidence_id
               WHERE e.case_id=%s AND d.source='AUTO_YOLO' AND d.verification_status='Unverified_Draft'
               ORDER BY d.confidence ASC LIMIT %s""", (case_id, limit))
        items = [dict(r) for r in await cur.fetchall()]
        cur = await db.execute(
            """SELECT d.verification_status AS s, COUNT(*) AS n FROM detections d
               JOIN evidence e ON e.id=d.evidence_id
               WHERE e.case_id=%s AND d.source='AUTO_YOLO' GROUP BY d.verification_status""", (case_id,))
        counts = {r["s"]: r["n"] for r in await cur.fetchall()}
        await db.commit()
    finally:
        await db.close()
    return {"items": items, "counts": counts}


# ── transcripts & text for the whole case ─────────────────────────────────────

def _term_key(kind: str, norm: str) -> str:
    return object_key(norm) if kind == "OBJECT" else match_key(kind, norm)


@router.get("/cases/{case_id}/transcripts")
async def case_transcripts(case_id: str) -> Dict[str, Any]:
    """
    Every speech transcript, PDF text and PDF-OCR text in the case, with the
    clues found in each passage and which of them also occur in OTHER evidence.
    """
    data = await _require_case(case_id)
    ctx = data["ctx"]

    # (evidence_id, kind, canonical key) -> matches that include that evidence
    index: Dict[tuple, List[Dict[str, Any]]] = {}
    for m in data["matches"]:
        for mem in m["members"]:
            key = (mem["evidence_id"], m["kind"], _term_key(m["kind"], mem.get("norm_value") or mem["value"]))
            index.setdefault(key, []).append(m)

    chunks_by_ev: Dict[str, List[Dict[str, Any]]] = {}
    for ch in ctx["chunks"]:
        chunks_by_ev.setdefault(ch["evidence_id"], []).append(ch)

    out_evidence = []
    for ev in ctx["evidence"]:
        rows = []
        for ch in chunks_by_ev.get(ev["id"], []):
            terms = []
            seen = set()
            for c in svc.chunk_terms(ch.get("content") or ""):
                value, norm, _ = svc._fix_plate(c.kind, c.value, c.norm, c.context)
                if (c.kind, norm) in seen:
                    continue
                seen.add((c.kind, norm))
                hits = index.get((ev["id"], c.kind, _term_key(c.kind, norm)), [])
                if c.kind == "KEYWORD" and not hits:
                    continue          # an unshared everyday word is not worth showing
                terms.append({
                    "kind": c.kind, "value": value,
                    "matches": [{
                        "id": m["id"], "strength": m["strength"], "score": m["score"],
                        "also_in": sorted({x["file_name"] for x in m["members"] if x["evidence_id"] != ev["id"]}),
                    } for m in hits],
                })
            st = ch.get("start_time")
            et = ch.get("end_time")
            rows.append({
                "id": ch["id"], "text": ch.get("content") or "", "page": ch.get("page_number"),
                "source": svc._chunk_source(ch.get("source_type")),
                "ocr": str(ch.get("source_type") or "").upper() == "PDF_OCR",
                "start_ms": int(float(st) * 1000) if st is not None else None,
                "end_ms": int(float(et) * 1000) if et is not None else None,
                "terms": terms,
            })
        out_evidence.append({
            "evidence_id": ev["id"], "file_name": ev["file_name"], "file_type": ev["file_type"],
            "analysis_status": ev.get("analysis_status") or "NOT_RUN",
            "transcription_status": ev.get("transcription_status"),
            "chunks": rows,
            "matched_terms": sum(1 for r in rows for t in r["terms"] if t["matches"]),
        })
    return {"evidence": out_evidence,
            "totals": {"passages": len(ctx["chunks"]),
                       "matched_terms": sum(e["matched_terms"] for e in out_evidence)}}


# ── global overview (Intelligence Strip) ──────────────────────────────────────

_ACTION_TEXT = {
    "UPLOAD_EVIDENCE": "Evidence uploaded",
    "DELETE_EVIDENCE": "Evidence deleted",
    "AUTO_ANALYSIS_COMPLETED": "Automatic analysis completed",
    "VLM_ROI_SCAN": "Regional scan performed",
    "FINDING_VERIFIED": "Finding verified by an investigator",
    "FINDING_EDITED": "Finding edited (verification reset)",
    "FINDING_VERIFICATION_REVOKED": "Finding verification revoked",
    "DETECTION_REVIEWED": "Detection reviewed",
    "REPORT_GENERATED": "Report generated",
    "EVIDENCE_LOCATION_SET": "Evidence location set",
    "EVIDENCE_HASH_RECORDED": "Evidence hash recorded",
    "AUDIT_PAYLOAD_VIEWED": "Raw model output viewed",
}


@router.get("/overview")
async def overview(max_cases: int = Query(12, ge=1, le=50)) -> Dict[str, Any]:
    """
    Real cross-case summary for the Intelligence Strip: strongest shared clues,
    concrete gaps in the evidence, and recent activity from the custody log.
    Nothing here is hypothesised — every item is computed from stored data.
    """
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT id, case_number, title, status FROM cases ORDER BY updated_at DESC LIMIT %s", (max_cases,))
        cases = [dict(r) for r in await cur.fetchall()]
        await db.commit()
    finally:
        await db.close()

    leads: List[Dict[str, Any]] = []
    gaps: List[Dict[str, Any]] = []
    stats = {"cases": len(cases), "evidence": 0, "clues": 0, "matches": 0}

    for c in cases:
        data = await svc.case_correlations(c["id"])
        if not data:
            continue
        ctx, evidence = data["ctx"], data["evidence"]
        stats["evidence"] += len(ctx["evidence"])
        stats["clues"] += len(data["clues"])
        stats["matches"] += len(data["matches"])
        label = f"{c['case_number']}"

        for m in data["matches"]:
            if m["strength"] == "WEAK":
                continue
            leads.append({
                "id": f"{c['id']}:{m['id']}", "case_id": c["id"], "case_number": c["case_number"],
                "case_title": c["title"], "kind": m["kind"], "value": m["value"],
                "strength": m["strength"], "score": m["score"], "match_type": m["match_type"],
                "explanation": m["explanation"], "verified": m["verified"],
                "files": sorted({x["file_name"] for x in m["members"]}),
                "sources": [{"file": x["file_name"], "at": x["timestamp_str"], "source": x["source"],
                             "reading": x["value"]} for x in m["members"]],
            })

        chunk_ev = {ch["evidence_id"] for ch in ctx["chunks"]}
        n_unreviewed = sum(1 for d in ctx["detections"]
                           if d.get("source") == "AUTO_YOLO" and d.get("verification_status") == "Unverified_Draft")
        n_drafts = sum(1 for d in ctx["detections"]
                       if d.get("source") == "VLM_ROI" and d.get("verification_status") != "Verified")

        def gap(sev: str, text: str, kind: str) -> None:
            gaps.append({"id": f"{c['id']}:{kind}:{len(gaps)}", "severity": sev, "text": text,
                         "case_id": c["id"], "case_number": label, "kind": kind})

        for e in ctx["evidence"]:
            st = e.get("analysis_status") or "NOT_RUN"
            if st in ("NOT_RUN", "FAILED"):
                gap("high" if st == "FAILED" else "medium",
                    f"{e['file_name']}: automatic analysis {'failed' if st == 'FAILED' else 'has not been run'}",
                    "analysis")
            if e["file_type"] in ("AUDIO", "VIDEO") and e["id"] not in chunk_ev \
                    and (e.get("transcription_status") or "PENDING") != "TRANSCRIBED":
                gap("low", f"{e['file_name']}: no speech transcript yet", "transcript")
            if e["file_type"] == "DOCUMENT" and e["id"] not in chunk_ev:
                gap("medium", f"{e['file_name']}: no text could be extracted", "document")
            if e.get("latitude") is None and e["file_type"] in ("VIDEO", "IMAGE") and \
                    any(e["id"] in m["evidence_ids"] for m in data["matches"] if m["strength"] != "WEAK"):
                gap("low", f"{e['file_name']}: matches other evidence but has no location", "location")
        if n_unreviewed:
            gap("low", f"{n_unreviewed} automatic detection(s) await review", "review")
        if n_drafts:
            gap("medium", f"{n_drafts} regional-scan finding(s) are still unverified drafts", "drafts")

    leads.sort(key=lambda x: -x["score"])
    order = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: order.get(g["severity"], 3))

    rows = await audit_engine.list_entries(limit=15)
    case_no = {c["id"]: c["case_number"] for c in cases}
    activity = [{
        "id": str(r["seq"]), "seq": r["seq"], "action": r["action"],
        "text": _ACTION_TEXT.get(r["action"], r["action"].replace("_", " ").capitalize()),
        "case_number": case_no.get(r.get("case_id")), "operator": r["operator_id"],
        "time": r["timestamp_utc"],
    } for r in rows]

    from backend.routes.citizens import all_alerts
    try:
        repeat = await all_alerts()
    except Exception:                       # the register is optional for the rest of the overview
        repeat = []
    return {"repeat_people": repeat, "leads": leads[:30], "gaps": gaps[:40], "activity": activity, "stats": stats}


# ── key findings (people / ids / items / vehicles) and the event timeline ─────

@router.get("/cases/{case_id}/key-findings")
async def key_findings(case_id: str) -> Dict[str, Any]:
    """
    Who, what and which vehicle: investigator-assigned roles first, automatic
    cues second, each with the supporting observations from other evidence.
    """
    data = await _require_case(case_id)
    summary = build_key_findings(data["ctx"], data["clues"], data["matches"])
    summary["case"] = {"id": case_id, "case_number": data["ctx"]["case"].get("case_number"),
                       "title": data["ctx"]["case"].get("title")}
    return summary


@router.get("/cases/{case_id}/event-timeline")
async def event_timeline(case_id: str, window_min: int = Query(45, ge=5, le=240)) -> Dict[str, Any]:
    """Chat, speech and video aligned on one wall-clock, plus the aligned groups."""
    data = await _require_case(case_id)
    result = build_event_timeline(data["ctx"], svc.chunk_terms, window_min=window_min)
    return result


class RecordingStartBody(BaseModel):
    recording_start: str = Field(min_length=5, max_length=19, description="YYYY-MM-DDTHH:MM:SS or HH:MM:SS")
    operator_id: str = Field(default="OPERATOR", min_length=1, max_length=100)


@router.put("/evidence/{evidence_id}/recording-start")
async def set_recording_start(evidence_id: str, body: RecordingStartBody) -> Dict[str, Any]:
    """Set the real clock time at which a recording started (overrides the burned-in clock reading)."""
    from backend.modules.clock import to_datetime
    if to_datetime(body.recording_start) is None:
        raise HTTPException(status_code=422, detail="Use YYYY-MM-DDTHH:MM:SS or HH:MM:SS")
    db = await get_db()
    try:
        cur = await db.execute("SELECT case_id, file_hash_sha256 FROM evidence WHERE id=%s", (evidence_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Evidence not found")
        await db.execute(
            "UPDATE evidence SET recording_start=%s, recording_start_source='manual' WHERE id=%s",
            (body.recording_start, evidence_id))
        await db.commit()
    finally:
        await db.close()
    await audit_engine.append_entry(
        "RECORDING_START_SET", operator_id=body.operator_id, case_id=row["case_id"], evidence_id=evidence_id,
        file_hash_sha256=row.get("file_hash_sha256"), metadata={"recording_start": body.recording_start})
    return {"evidence_id": evidence_id, "recording_start": body.recording_start, "source": "manual"}


# ── people involved: the investigator chooses victim / suspects / guilty ──────

_PERSON_ROLES = ("UNASSIGNED", "VICTIM", "SUSPECT", "PERSON_OF_INTEREST", "WITNESS", "CLEARED", "GUILTY")


class PersonDesignationBody(BaseModel):
    """
    The investigator's decision about one person.

    GUILTY is deliberately hard to set: it must be confirmed explicitly and
    carry a written basis. It records the investigator's own determination,
    attributed to them and audited — ForenSight never suggests or infers it.
    """
    role: str = Field(default="UNASSIGNED")
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=190)
    basis: Optional[str] = Field(default=None, max_length=4000)
    aliases: List[str] = Field(default_factory=list, max_length=60)   # other names / ID values of this person
    operator_id: str = Field(min_length=1, max_length=100)
    confirm_determination: bool = False

    def check(self) -> None:
        if self.role not in _PERSON_ROLES:
            raise HTTPException(status_code=422, detail=f"role must be one of {', '.join(_PERSON_ROLES)}")
        if self.role == "GUILTY":
            if not self.confirm_determination:
                raise HTTPException(status_code=422, detail=(
                    "Designating a person as guilty is YOUR determination, not a finding of this system. "
                    "Set confirm_determination=true to record it."))
            if not self.basis or len(self.basis.strip()) < 20:
                raise HTTPException(status_code=422, detail=(
                    "A written basis (at least 20 characters) is required for a guilty designation."))


class NewPersonBody(BaseModel):
    name: str = Field(min_length=2, max_length=190)
    identifiers: List[str] = Field(default_factory=list, max_length=20)
    operator_id: str = Field(min_length=1, max_length=100)


def _person_key_for(name: str) -> str:
    from backend.modules.people_roster import norm_name
    return "p:" + re.sub(r"\s+", "-", norm_name(name))


async def _roster_for(case_id: str) -> List[Dict[str, Any]]:
    from backend.modules.people_roster import build_roster
    data = await _require_case(case_id)
    return build_roster(data["ctx"], data["clues"], data["matches"], data["ctx"].get("designations", []))


@router.get("/cases/{case_id}/people")
async def case_people(case_id: str) -> Dict[str, Any]:
    """Everyone involved, found from names, chat authors, badges and ID cards in the evidence."""
    roster = await _roster_for(case_id)

    # Match against the citizen register (suggestions only) and flag people who recur across cases.
    from backend.routes import citizens as citizen_routes
    citizens = await citizen_routes.load_citizens()
    links = await citizen_routes.refresh_case_links(case_id, roster, citizens) if citizens else {}
    counts = await citizen_routes.citizen_case_counts() if citizens else {}
    by_id = {c["id"]: c for c in citizens}
    repeat = []
    for p in roster:
        matches = []
        for m in links.get(p["key"], []):
            if m["status"] == "REJECTED":
                continue
            c = by_id.get(m["citizen_id"], {})
            n = counts.get(m["citizen_id"], 0)
            others = []
            if n >= 2:
                others = [l for l in await citizen_routes._links_for_citizen(m["citizen_id"])
                          if l["case_id"] != case_id and l["counts_for_alert"]]
            matches.append({
                **m, "photo_url": f"/api/v1/citizens/{m['citizen_id']}/photo", "citizen_status": c.get("status"),
                "criminal_record": c.get("criminal_record"), "case_count": n, "other_cases": others,
            })
            if others and m["status"] in ("CONFIRMED", "SUGGESTED"):
                repeat.append({"person_key": p["key"], "person_name": p["name"], "citizen_id": m["citizen_id"],
                               "citizen_name": m["full_name"], "status": m["status"],
                               "other_cases": [{"case_id": o["case_id"], "case_number": o["case_number"],
                                                "role": o["role"]} for o in others]})
        p["citizen_matches"] = matches
    return {
        "repeat_people": repeat,
        "people": roster,
        "roles": list(_PERSON_ROLES),
        "totals": {
            "people": len(roster),
            "designated": sum(1 for p in roster if p["role"]),
            "unassigned": sum(1 for p in roster if not p["role"]),
            "with_badge_or_id": sum(1 for p in roster if p["identifiers"]),
        },
        "notice": ("Roles you assign are the investigator's own designations and are recorded with your ID and "
                   "time. The system only suggests victim / suspect / witness from nearby words; it never "
                   "suggests or decides guilt."),
    }


async def _upsert_designation(case_id: str, key: str, body: PersonDesignationBody, manual: bool = False) -> Dict[str, Any]:
    from backend.modules.people_roster import _json_list, norm_name
    body.check()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db = await get_db()
    try:
        cur = await db.execute("SELECT id FROM cases WHERE id=%s", (case_id,))
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Case not found")
        cur = await db.execute("SELECT * FROM person_designations WHERE case_id=%s AND person_key=%s", (case_id, key))
        old = await cur.fetchone()
        aliases = sorted({a.strip() for a in (list(_json_list(old["aliases"])) if old else []) + body.aliases if a.strip()})
        name = body.display_name or (old["display_name"] if old else None) or key.split(":", 1)[-1].replace("-", " ").title()
        if old:
            await db.execute(
                """UPDATE person_designations
                   SET display_name=%s, role=%s, basis=%s, aliases=%s, designated_by=%s, designated_at=%s
                   WHERE id=%s""",
                (name, body.role, body.basis, json.dumps(aliases), body.operator_id, now, old["id"]))
        else:
            await db.execute(
                """INSERT INTO person_designations
                   (id, case_id, person_key, display_name, role, basis, aliases, is_manual, designated_by, designated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (uuid.uuid4().hex, case_id, key, name, body.role, body.basis, json.dumps(aliases),
                 1 if manual else 0, body.operator_id, now))
        await db.commit()
    finally:
        await db.close()

    await audit_engine.append_entry(
        "PERSON_DESIGNATED", operator_id=body.operator_id, case_id=case_id,
        metadata={"person_key": key, "display_name": name, "role": body.role,
                  "previous_role": old["role"] if old else None, "basis": body.basis, "aliases": aliases,
                  "determination_by_investigator": body.role == "GUILTY"})
    return {"person_key": key, "display_name": name, "role": body.role, "designated_by": body.operator_id,
            "designated_at": now, "aliases": aliases}


@router.put("/cases/{case_id}/people/{person_key:path}")
async def designate_person(case_id: str, person_key: str, body: PersonDesignationBody) -> Dict[str, Any]:
    return await _upsert_designation(case_id, person_key, body)


@router.post("/cases/{case_id}/people", status_code=201)
async def add_person(case_id: str, body: NewPersonBody) -> Dict[str, Any]:
    """Add someone who is not (yet) named in any evidence, optionally with badge / ID values."""
    key = _person_key_for(body.name)
    designation = PersonDesignationBody(role="UNASSIGNED", display_name=body.name.strip(), aliases=body.identifiers,
                                        operator_id=body.operator_id)
    return await _upsert_designation(case_id, key, designation, manual=True)


@router.delete("/cases/{case_id}/people/{person_key:path}")
async def clear_person(case_id: str, person_key: str, operator_id: str = Query("OPERATOR", min_length=1)) -> Dict[str, Any]:
    """Remove the investigator's designation (manual people disappear; found people go back to unassigned)."""
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM person_designations WHERE case_id=%s AND person_key=%s",
                               (case_id, person_key))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No designation for this person")
        await db.execute("DELETE FROM person_designations WHERE id=%s", (row["id"],))
        await db.commit()
    finally:
        await db.close()
    await audit_engine.append_entry(
        "PERSON_DESIGNATION_CLEARED", operator_id=operator_id, case_id=case_id,
        metadata={"person_key": person_key, "previous_role": row["role"], "display_name": row["display_name"]})
    return {"person_key": person_key, "cleared": True}


class AliasBody(BaseModel):
    aliases: List[str] = Field(min_length=1, max_length=40)       # other names / badge / ID values of this person
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=190)
    operator_id: str = Field(min_length=1, max_length=100)


@router.post("/cases/{case_id}/people/{person_key:path}/aliases")
async def add_person_aliases(case_id: str, person_key: str, body: AliasBody) -> Dict[str, Any]:
    """
    Declare that more names / badge or ID values belong to this person ("same person as...",
    "this ID card is theirs"). Does not change their role.
    """
    from backend.modules.people_roster import _json_list
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM person_designations WHERE case_id=%s AND person_key=%s",
                               (case_id, person_key))
        row = await cur.fetchone()
        merged = sorted({a.strip() for a in (_json_list(row["aliases"]) if row else []) + body.aliases if a.strip()})
        if row:
            await db.execute("UPDATE person_designations SET aliases=%s WHERE id=%s", (json.dumps(merged), row["id"]))
        else:
            name = body.display_name or person_key.split(":", 1)[-1].replace("-", " ").title()
            await db.execute(
                """INSERT INTO person_designations
                   (id, case_id, person_key, display_name, role, aliases, is_manual, designated_by, designated_at)
                   VALUES (%s,%s,%s,%s,'UNASSIGNED',%s,0,%s,%s)""",
                (uuid.uuid4().hex, case_id, person_key, name, json.dumps(merged), body.operator_id, now))
        await db.commit()
    finally:
        await db.close()
    await audit_engine.append_entry(
        "PERSON_ALIASES_ADDED", operator_id=body.operator_id, case_id=case_id,
        metadata={"person_key": person_key, "added": body.aliases})
    return {"person_key": person_key, "aliases": merged}
