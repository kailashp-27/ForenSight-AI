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
               VALUES (?, ?, ?, ?, ?)""",
            (case_id, case_number, payload.title, payload.description, payload.created_by_name),
        )
        await db.commit()
        row = await db.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
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


@router.get("/{case_id}")
async def get_case(case_id: str):
    db = await get_db()
    try:
        row = await db.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
        case = _row_to_dict(await row.fetchone())
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        ev_cursor = await db.execute(
            "SELECT * FROM evidence WHERE case_id = ? ORDER BY uploaded_at DESC",
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
        row = await db.execute("SELECT id FROM cases WHERE id = ?", (case_id,))
        if not await row.fetchone():
            raise HTTPException(status_code=404, detail="Case not found")

        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [datetime.utcnow().isoformat(), case_id]
        await db.execute(
            f"UPDATE cases SET {set_clause}, updated_at = ? WHERE id = ?", values
        )
        await db.commit()
        row = await db.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
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
        row = await db.execute("SELECT id FROM cases WHERE id = ?", (case_id,))
        if not await row.fetchone():
            raise HTTPException(status_code=404, detail="Case not found")
        await db.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        await db.commit()
    finally:
        await db.close()

    await write_audit_log(
        action="DELETE_CASE",
        case_id=case_id,
        ip_address=request.client.host if request.client else None,
    )
