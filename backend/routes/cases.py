"""
backend/routes/cases.py
────────────────────────
Case management API routes.

Endpoints:
  POST   /api/cases          → Create a new investigation case
  GET    /api/cases          → List all cases (with evidence count)
  GET    /api/cases/{id}     → Get a single case with its evidence list
  PATCH  /api/cases/{id}     → Update case status or title
  DELETE /api/cases/{id}     → Delete / archive a case
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.database.db import get_db, write_audit_log

router = APIRouter()


# ── Pydantic Schemas ────────────────────────────────────────────────────────

class CaseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    case_number: Optional[str] = None     # auto-generated if omitted
    created_by_name: Optional[str] = "Investigator"


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None          # OPEN | UNDER_REVIEW | CLOSED | ARCHIVED


# ── Helpers ─────────────────────────────────────────────────────────────────

def _generate_case_number() -> str:
    """Auto-generate a case number like FS-2026-0001."""
    now = datetime.utcnow()
    suffix = uuid.uuid4().hex[:4].upper()
    return f"FS-{now.year}-{suffix}"


def _row_to_dict(row) -> dict:
    return dict(row) if row else None


# ── Routes ──────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_case(payload: CaseCreate, request: Request):
    case_id = uuid.uuid4().hex
    case_number = payload.case_number or _generate_case_number()

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO cases (id, case_number, title, description, created_by_name)
               VALUES (%s, %s, %s, %s, %s)""",
            (case_id, case_number, payload.title, payload.description, payload.created_by_name),
        )
        await db.commit()
        row = await db.execute("SELECT * FROM cases WHERE id = %s", (case_id,))
        case = _row_to_dict(await row.fetchone())
    finally:
        await db.close()

    await write_audit_log(
        action="CREATE_CASE",
        case_id=case_id,
        metadata={"case_number": case_number, "title": payload.title},
        ip_address=request.client.host if request.client else None,
    )

    return case


@router.get("")
async def list_cases():
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT c.*,
                      COUNT(e.id) AS evidence_count
               FROM cases c
               LEFT JOIN evidence e ON e.case_id = c.id
               GROUP BY c.id
               ORDER BY c.created_at DESC"""
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    return [dict(r) for r in rows]


@router.get("/fix-dates-temp")
async def fix_dates_temp():
    db = await get_db()
    try:
        await db.execute("UPDATE cases SET created_at = '2026-08-01 10:00:00' WHERE case_number = 'CASE-2026-001'")
        
        # Get evidence
        ev_cur = await db.execute("SELECT id FROM evidence WHERE case_id = (SELECT id FROM cases WHERE case_number = 'CASE-2026-001')")
        evidence = await ev_cur.fetchall()
        
        dates = ['2026-08-10 14:30:00', '2026-08-25 09:15:00', '2026-09-05 11:20:00', '2026-09-14 16:45:00']
        for i, ev in enumerate(evidence):
            await db.execute("UPDATE evidence SET uploaded_at = %s WHERE id = %s", (dates[i % len(dates)], ev['id']))
            
        det_cur = await db.execute("SELECT id FROM detections WHERE evidence_id IN (SELECT id FROM evidence WHERE case_id = (SELECT id FROM cases WHERE case_number = 'CASE-2026-001'))")
        detections = await det_cur.fetchall()
        
        for i, det in enumerate(detections):
            await db.execute("UPDATE detections SET created_at = %s WHERE id = %s", (dates[(i + 2) % len(dates)], det['id']))
            
        await db.commit()
        return {"status": "fixed"}
    finally:
        await db.close()

@router.get("/{case_id}")
async def get_case(case_id: str):
    db = await get_db()
    try:
        row = await db.execute("SELECT * FROM cases WHERE id = %s", (case_id,))
        case = _row_to_dict(await row.fetchone())
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        ev_cursor = await db.execute(
            "SELECT * FROM evidence WHERE case_id = %s ORDER BY uploaded_at DESC",
            (case_id,),
        )
        evidence = [dict(r) for r in await ev_cursor.fetchall()]
    finally:
        await db.close()

    case["evidence"] = evidence
    return case


@router.patch("/{case_id}")
async def update_case(case_id: str, payload: CaseUpdate, request: Request):
    db = await get_db()
    try:
        row = await db.execute("SELECT id FROM cases WHERE id = %s", (case_id,))
        if not await row.fetchone():
            raise HTTPException(status_code=404, detail="Case not found")

        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [datetime.utcnow().isoformat(), case_id]
        await db.execute(
            f"UPDATE cases SET {set_clause}, updated_at = %s WHERE id = %s", values
        )
        await db.commit()
        row = await db.execute("SELECT * FROM cases WHERE id = %s", (case_id,))
        case = _row_to_dict(await row.fetchone())
    finally:
        await db.close()

    await write_audit_log(
        action="UPDATE_CASE",
        case_id=case_id,
        metadata=updates,
        ip_address=request.client.host if request.client else None,
    )
    return case


@router.delete("/{case_id}", status_code=204)
async def delete_case(case_id: str, request: Request):
    db = await get_db()
    try:
        row = await db.execute("SELECT id FROM cases WHERE id = %s", (case_id,))
        if not await row.fetchone():
            raise HTTPException(status_code=404, detail="Case not found")
        await db.execute("DELETE FROM cases WHERE id = %s", (case_id,))
        await db.commit()
    finally:
        await db.close()

    await write_audit_log(
        action="DELETE_CASE",
        case_id=case_id,
        ip_address=request.client.host if request.client else None,
    )


@router.get("/{case_id}/timeline")
async def get_case_timeline(case_id: str):
    """
    Build a chronological timeline of events for a case from real DB data.
    Sources:
      1. Evidence upload records  → document / detection events
      2. Detections from AI       → detection / alert events
    Returns events sorted by created_at with a 0-100 relative `timestamp` field.
    """
    db = await get_db()
    try:
        row = await db.execute("SELECT id, case_number, created_at, created_by_name FROM cases WHERE id = %s", (case_id,))
        case = await row.fetchone()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        case = dict(case)

        ev_cursor = await db.execute(
            "SELECT id, file_name, file_type, uploaded_at, status FROM evidence WHERE case_id = %s ORDER BY uploaded_at",
            (case_id,),
        )
        evidence_rows = [dict(r) for r in await ev_cursor.fetchall()]

        det_cursor = await db.execute(
            """
            SELECT d.id, d.label, d.confidence, d.created_at, e.file_name, e.file_type
            FROM detections d
            JOIN evidence e ON d.evidence_id = e.id
            WHERE e.case_id = %s
            ORDER BY d.created_at
            """,
            (case_id,),
        )
        detection_rows = [dict(r) for r in await det_cursor.fetchall()]
    finally:
        await db.close()

    FILE_TYPE_TO_EVENT = {
        "IMAGE":    ("document",  "Image uploaded",   "person"),
        "VIDEO":    ("detection", "Video uploaded",   "device"),
        "AUDIO":    ("document",  "Audio uploaded",   "device"),
        "DOCUMENT": ("document",  "Document uploaded","person"),
        "OTHER":    ("document",  "File uploaded",    "person"),
    }

    raw: list[dict] = []

    # 1. Add "Case Created" root event
    raw.append({
        "id":          f"case-{case['id'][:8]}",
        "label":       "Case Created",
        "type":        "document",
        "time_iso":    case["created_at"],
        "entity":      case["created_by_name"],
        "entityType":  "person",
        "risk":        None,
        "description": f"Case {case['case_number']} opened by {case['created_by_name']}",
    })

    for ev in evidence_rows:
        ev_type, ev_label_prefix, entity_type = FILE_TYPE_TO_EVENT.get(ev["file_type"], ("document", "File uploaded", "person"))
        raw.append({
            "id":          f"ev-{ev['id'][:8]}",
            "label":       f"{ev_label_prefix}: {ev['file_name'][:22]}",
            "type":        ev_type,
            "time_iso":    ev["uploaded_at"],
            "entity":      ev["file_name"][:16],
            "entityType":  entity_type,
            "risk":        None,
            "description": f"{ev['file_type']} evidence — status: {ev['status']}",
        })

    for det in detection_rows:
        confidence = float(det["confidence"] or 0)
        risk = "high" if confidence >= 0.75 else ("medium" if confidence >= 0.5 else "low")
        raw.append({
            "id":          f"det-{det['id'][:8]}",
            "label":       det["label"][:28],
            "type":        "detection",
            "time_iso":    det["created_at"],
            "entity":      det["file_name"][:16],
            "entityType":  "device",
            "risk":        risk,
            "description": f"AI detection in {det['file_name']} — confidence {confidence:.0%}",
        })

    def _ts(iso: str) -> float:
        from datetime import datetime
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0

    raw.sort(key=lambda e: _ts(e["time_iso"]))



    if not raw:
        return []

    t_min = _ts(raw[0]["time_iso"])
    t_max = _ts(raw[-1]["time_iso"])
    span  = t_max - t_min if t_max > t_min else 1.0

    from datetime import datetime
    events = []
    for i, r in enumerate(raw):
        rel = round(((_ts(r["time_iso"]) - t_min) / span) * 90 + 5, 1)
        try:
            time_label = datetime.fromisoformat(r["time_iso"].replace("Z", "+00:00")).strftime("%H:%M")
        except Exception:
            time_label = f"T{i}"

        events.append({
            "id":          r["id"],
            "label":       r["label"],
            "type":        r["type"],
            "time":        time_label,
            "timestamp":   rel,
            "entity":      r["entity"],
            "entityType":  r["entityType"],
            "risk":        r["risk"],
            "description": r["description"],
        })

    return events


