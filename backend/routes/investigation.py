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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.database.db import get_db
from backend.modules import audit_engine, auto_analysis, investigation_service as svc
from backend.modules.report_engine import build_report_html

router = APIRouter()


class LocationBody(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    label: Optional[str] = Field(default=None, max_length=255)
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
            "weak": sum(m["strength"] == "WEAK" for m in data["matches"]),
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
        elif d.get("source") == "AUTO_YOLO":
            auto.append({"evidence_id": d["evidence_id"], "label": d["label"],
                         "timestamp_str": d.get("timestamp_str"), "confidence": d["confidence"]})

    chain = await audit_engine.verify_chain()
    html_doc = build_report_html({
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
