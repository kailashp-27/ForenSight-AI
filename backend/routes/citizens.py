"""
backend/routes/citizens.py
──────────────────────────
Citizen register (reference database of people) and its links to case people.

  GET  /api/v1/citizens                      list + search (name, id, phone, address, occupation, record)
  GET  /api/v1/citizens/alerts               citizens who appear in 2+ cases
  GET  /api/v1/citizens/{id}                 the full file (details, linked cases, alerts)
  GET  /api/v1/citizens/{id}/photo           photo, or a generated placeholder image
  PUT  /api/v1/citizens/{id}/photo           upload a real photo (jpg/png)
  POST /api/v1/cases/{case}/people/{key}/citizen-match   confirm / reject a suggested link

Links between a case person and a citizen are SUGGESTIONS until an investigator
confirms them (names are shared between people). A rejected pairing is never
suggested again. A citizen counts toward a cross-case alert when the link is
confirmed, or suggested at LIKELY or above.
"""

from __future__ import annotations

import colorsys
import hashlib
import json
import re
import uuid
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from backend.config import settings
from backend.database.db import get_db
from backend.modules import audit_engine
from backend.modules.citizen_match import ALERT_THRESHOLD, candidates_for, tokens

router = APIRouter()

PHOTO_DIR = Path(settings.STORAGE_DIR) / "citizens"
SUSPECT_ROLES = {"SUSPECT", "PERSON_OF_INTEREST", "GUILTY"}
_MAX_PHOTO = 5 * 1024 * 1024


def _iso(v: Any) -> Optional[str]:
    if isinstance(v, (date, datetime)):
        return v.isoformat()[:10]
    return str(v)[:10] if v else None


def _age(dob: Any) -> Optional[int]:
    s = _iso(dob)
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date() if s else None
    except ValueError:
        return None
    if not d:
        return None
    t = date.today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))


def _row(c: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": c["id"], "full_name": c["full_name"], "dob": _iso(c.get("dob")), "age": _age(c.get("dob")),
        "phone": c.get("phone"), "address": c.get("address"), "occupation": c.get("occupation"),
        "criminal_record": c.get("criminal_record"), "status": c.get("status"),
        "has_record": (c.get("criminal_record") or "None").strip().lower() not in ("none", ""),
        "has_photo": bool(c.get("photo_path")),
        "photo_url": f"/api/v1/citizens/{c['id']}/photo",
    }


# ── link bookkeeping (used by the People endpoint too) ───────────────────────

async def load_citizens() -> List[Dict[str, Any]]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM citizens ORDER BY id")
        rows = [dict(r) for r in await cur.fetchall()]
        await db.commit()
    finally:
        await db.close()
    return rows


async def refresh_case_links(case_id: str, roster: List[Dict[str, Any]], citizens: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Recompute suggestions for every person in a case, keep the investigator's
    confirmed / rejected decisions, drop stale suggestions, and return, per
    person_key, the current candidate links (with decision status).
    """
    if not citizens:
        return {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM citizen_links WHERE case_id=%s", (case_id,))
        existing = [dict(r) for r in await cur.fetchall()]
        by_key: Dict[tuple, Dict[str, Any]] = {(r["person_key"], r["citizen_id"]): r for r in existing}
        rejected: Dict[str, set] = {}
        for r in existing:
            if r["status"] == "REJECTED":
                rejected.setdefault(r["person_key"], set()).add(r["citizen_id"])

        keep: set = set()
        result: Dict[str, List[Dict[str, Any]]] = {}
        for p in roster:
            cands = candidates_for(p, citizens, rejected=rejected.get(p["key"], ()))
            for cd in cands:
                key = (p["key"], cd["citizen_id"])
                keep.add(key)
                row = by_key.get(key)
                if row:
                    await db.execute(
                        """UPDATE citizen_links SET score=%s, level=%s, reasons=%s, person_name=%s, person_role=%s
                           WHERE id=%s""",
                        (cd["score"], cd["level"], json.dumps(cd["reasons"]), p["name"], p.get("role"), row["id"]))
                    status = row["status"]
                else:
                    await db.execute(
                        """INSERT INTO citizen_links
                           (id, case_id, person_key, person_name, person_role, citizen_id, status, score, level, reasons)
                           VALUES (%s,%s,%s,%s,%s,%s,'SUGGESTED',%s,%s,%s)""",
                        (uuid.uuid4().hex, case_id, p["key"], p["name"], p.get("role"), cd["citizen_id"],
                         cd["score"], cd["level"], json.dumps(cd["reasons"])))
                    status = "SUGGESTED"
                result.setdefault(p["key"], []).append({**cd, "status": status})
        # confirmed links stay visible even if the matcher would no longer suggest them
        for r in existing:
            k = (r["person_key"], r["citizen_id"])
            if r["status"] == "CONFIRMED" and k not in keep:
                keep.add(k)
                result.setdefault(r["person_key"], []).append({
                    "citizen_id": r["citizen_id"], "full_name": next((c["full_name"] for c in citizens if c["id"] == r["citizen_id"]), "?"),
                    "score": r["score"], "level": r["level"], "reasons": json.loads(r["reasons"] or "[]"), "status": "CONFIRMED"})
        # stale suggestions (person gone / no longer matches) must not raise alerts
        for r in existing:
            if r["status"] == "SUGGESTED" and (r["person_key"], r["citizen_id"]) not in keep:
                await db.execute("DELETE FROM citizen_links WHERE id=%s", (r["id"],))
        await db.commit()
    finally:
        await db.close()
    return result


async def citizen_case_counts() -> Dict[int, int]:
    """citizen_id -> number of distinct cases it counts toward (confirmed, or suggested LIKELY+)."""
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT citizen_id, COUNT(DISTINCT case_id) AS n FROM citizen_links
               WHERE status='CONFIRMED' OR (status='SUGGESTED' AND score >= %s)
               GROUP BY citizen_id""", (ALERT_THRESHOLD,))
        out = {int(r["citizen_id"]): int(r["n"]) for r in await cur.fetchall()}
        await db.commit()
    finally:
        await db.close()
    return out


async def _links_for_citizen(citizen_id: int) -> List[Dict[str, Any]]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT l.*, c.case_number, c.title AS case_title, c.status AS case_status,
                      d.role AS designated_role
               FROM citizen_links l
               JOIN cases c ON c.id = l.case_id
               LEFT JOIN person_designations d ON d.case_id = l.case_id AND d.person_key = l.person_key
               WHERE l.citizen_id=%s AND l.status <> 'REJECTED'
               ORDER BY l.score DESC""", (citizen_id,))
        rows = [dict(r) for r in await cur.fetchall()]
        await db.commit()
    finally:
        await db.close()
    out = []
    for r in rows:
        role = r.get("designated_role") if r.get("designated_role") not in (None, "UNASSIGNED") else r.get("person_role")
        counts = r["status"] == "CONFIRMED" or float(r["score"] or 0) >= ALERT_THRESHOLD
        out.append({
            "case_id": r["case_id"], "case_number": r["case_number"], "case_title": r["case_title"],
            "case_status": r["case_status"], "person_key": r["person_key"], "person_name": r["person_name"],
            "role": role, "status": r["status"], "score": float(r["score"] or 0), "level": r["level"],
            "reasons": json.loads(r["reasons"] or "[]"), "counts_for_alert": counts,
        })
    return out


def _alert_from(citizen: Dict[str, Any], links: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    counted = [l for l in links if l["counts_for_alert"]]
    cases = {l["case_id"] for l in counted}
    if len(cases) < 2:
        return None
    confirmed_cases = {l["case_id"] for l in counted if l["status"] == "CONFIRMED"}
    suspect_cases = {l["case_id"] for l in counted if l["role"] in SUSPECT_ROLES}
    priority = "HIGH" if len(confirmed_cases) >= 2 or len(suspect_cases) >= 2 else "MEDIUM"
    return {
        "citizen_id": citizen["id"], "full_name": citizen["full_name"], "status": citizen.get("status"),
        "criminal_record": citizen.get("criminal_record"), "photo_url": f"/api/v1/citizens/{citizen['id']}/photo",
        "case_count": len(cases), "confirmed_cases": len(confirmed_cases), "suspect_cases": len(suspect_cases),
        "priority": priority,
        "cases": sorted(counted, key=lambda l: (l["case_number"] or "")),
        "message": (f"{citizen['full_name']} is linked to {len(cases)} cases"
                    + (f" ({len(confirmed_cases)} confirmed)" if confirmed_cases else " (suggested, unconfirmed)")
                    + (f", as a suspect in {len(suspect_cases)}" if suspect_cases else "")),
    }


async def all_alerts() -> List[Dict[str, Any]]:
    counts = await citizen_case_counts()
    multi = [cid for cid, n in counts.items() if n >= 2]
    if not multi:
        return []
    citizens = {c["id"]: c for c in await load_citizens()}
    out = []
    for cid in multi:
        if cid in citizens:
            a = _alert_from(citizens[cid], await _links_for_citizen(cid))
            if a:
                out.append(a)
    out.sort(key=lambda a: (a["priority"] != "HIGH", -a["case_count"], a["full_name"]))
    return out


# ── routes ───────────────────────────────────────────────────────────────────

@router.get("/citizens")
async def list_citizens(
    q: str = Query("", max_length=100),
    status: Optional[str] = None,
    has_record: Optional[bool] = None,
    multi_case: bool = False,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    rows = await load_citizens()
    counts = await citizen_case_counts()
    needle = q.strip().lower()
    digits = re.sub(r"\D", "", needle)

    def hit(c: Dict[str, Any]) -> bool:
        if not needle:
            return True
        hay = " ".join(str(c.get(k) or "") for k in ("full_name", "address", "occupation", "criminal_record", "status")).lower()
        return (needle in hay or needle == str(c["id"])
                or (len(digits) >= 3 and digits in re.sub(r"\D", "", c.get("phone") or "")))

    items = []
    for c in rows:
        r = _row(c)
        r["case_count"] = counts.get(c["id"], 0)
        r["multi_case"] = r["case_count"] >= 2
        if not hit(c):
            continue
        if status and (c.get("status") or "").lower() != status.lower():
            continue
        if has_record is not None and r["has_record"] != has_record:
            continue
        if multi_case and not r["multi_case"]:
            continue
        items.append(r)
    statuses = sorted({c.get("status") or "Unknown" for c in rows})
    return {"total": len(items), "items": items[offset: offset + limit], "statuses": statuses,
            "multi_case_total": sum(1 for v in counts.values() if v >= 2)}


@router.get("/citizens/alerts")
async def citizen_alerts() -> Dict[str, Any]:
    alerts = await all_alerts()
    return {"alerts": alerts, "count": len(alerts), "high": sum(1 for a in alerts if a["priority"] == "HIGH")}


@router.get("/citizens/{citizen_id}")
async def citizen_file(citizen_id: int) -> Dict[str, Any]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM citizens WHERE id=%s", (citizen_id,))
        row = await cur.fetchone()
        await db.commit()
    finally:
        await db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Citizen not found")
    c = dict(row)
    links = await _links_for_citizen(citizen_id)
    return {**_row(c), "links": links, "alert": _alert_from(c, links),
            "notice": ("Reference record from the citizen register. A link to a case person is only a suggestion "
                       "until an investigator confirms it; a shared name is not an identification.")}


def _placeholder_svg(cid: int, name: str) -> str:
    parts = [p for p in re.sub(r"[^A-Za-z ]+", " ", name).split() if p]
    initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper() if parts else "?"
    hue = int(hashlib.sha1(f"{cid}{name}".encode()).hexdigest()[:4], 16) / 0xFFFF
    r, g, b = (int(x * 255) for x in colorsys.hls_to_rgb(hue, 0.30, 0.35))
    bg = f"#{r:02x}{g:02x}{b:02x}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 360" role="img" aria-label="No photo for {escape(name)}">'
        f'<rect width="300" height="360" fill="{bg}"/>'
        f'<circle cx="150" cy="130" r="58" fill="rgba(255,255,255,0.22)"/>'
        f'<path d="M40 360c0-76 50-118 110-118s110 42 110 118z" fill="rgba(255,255,255,0.22)"/>'
        f'<text x="150" y="150" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="52" '
        f'font-weight="700" fill="#ffffff">{escape(initials)}</text>'
        f'<rect x="0" y="318" width="300" height="42" fill="rgba(0,0,0,0.45)"/>'
        f'<text x="150" y="345" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="16" '
        f'letter-spacing="3" fill="#e2e8f0">PHOTO NOT AVAILABLE</text></svg>'
    )


@router.get("/citizens/{citizen_id}/photo")
async def citizen_photo(citizen_id: int):
    db = await get_db()
    try:
        cur = await db.execute("SELECT full_name, photo_path FROM citizens WHERE id=%s", (citizen_id,))
        row = await cur.fetchone()
        await db.commit()
    finally:
        await db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Citizen not found")
    if row["photo_path"] and Path(row["photo_path"]).is_file():
        return FileResponse(row["photo_path"], media_type="image/jpeg", headers={"Cache-Control": "no-cache"})
    return Response(content=_placeholder_svg(citizen_id, row["full_name"]), media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=3600"})


@router.put("/citizens/{citizen_id}/photo")
async def upload_citizen_photo(citizen_id: int, file: UploadFile = File(...), operator_id: str = Query("OPERATOR")) -> Dict[str, Any]:
    """Store a real photo (used later for matching). Re-encoded to JPEG so only valid images are kept."""
    data = await file.read()
    if len(data) > _MAX_PHOTO:
        raise HTTPException(status_code=413, detail="Photo must be 5 MB or smaller")

    def _encode() -> bytes:
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("The file is not a readable image")
        h, w = img.shape[:2]
        if max(h, w) > 1200:
            s = 1200 / max(h, w)
            img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return buf.tobytes()

    try:
        jpg = await run_in_threadpool(_encode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    path = PHOTO_DIR / f"{citizen_id}.jpg"
    path.write_bytes(jpg)
    db = await get_db()
    try:
        cur = await db.execute("SELECT id FROM citizens WHERE id=%s", (citizen_id,))
        if not await cur.fetchone():
            path.unlink(missing_ok=True)
            raise HTTPException(status_code=404, detail="Citizen not found")
        await db.execute("UPDATE citizens SET photo_path=%s WHERE id=%s", (str(path), citizen_id))
        await db.commit()
    finally:
        await db.close()
    await audit_engine.append_entry("CITIZEN_PHOTO_SET", operator_id=operator_id,
                                    metadata={"citizen_id": citizen_id, "sha256": hashlib.sha256(jpg).hexdigest()})
    return {"citizen_id": citizen_id, "photo_url": f"/api/v1/citizens/{citizen_id}/photo"}


class MatchDecision(BaseModel):
    citizen_id: int
    decision: str = Field(pattern="^(confirm|reject|reset)$")
    operator_id: str = Field(min_length=1, max_length=100)


@router.post("/cases/{case_id}/people/{person_key:path}/citizen-match")
async def decide_match(case_id: str, person_key: str, body: MatchDecision) -> Dict[str, Any]:
    """Investigator confirms that a case person IS this citizen, or that they are NOT."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status = {"confirm": "CONFIRMED", "reject": "REJECTED", "reset": "SUGGESTED"}[body.decision]
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM citizen_links WHERE case_id=%s AND person_key=%s AND citizen_id=%s",
                               (case_id, person_key, body.citizen_id))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No such suggested link; reload the People tab")
        await db.execute("UPDATE citizen_links SET status=%s, decided_by=%s, decided_at=%s WHERE id=%s",
                         (status, body.operator_id, now, row["id"]))
        if body.decision == "confirm":      # one person is one citizen: other suggestions for them fall away
            await db.execute(
                """UPDATE citizen_links SET status='REJECTED', decided_by=%s, decided_at=%s
                   WHERE case_id=%s AND person_key=%s AND citizen_id<>%s AND status='SUGGESTED'""",
                (body.operator_id, now, case_id, person_key, body.citizen_id))
        await db.commit()
    finally:
        await db.close()
    await audit_engine.append_entry(
        "CITIZEN_LINK_DECIDED", operator_id=body.operator_id, case_id=case_id,
        metadata={"person_key": person_key, "citizen_id": body.citizen_id, "decision": body.decision,
                  "person_name": row["person_name"], "score": float(row["score"] or 0)})
    return {"person_key": person_key, "citizen_id": body.citizen_id, "status": status, "decided_by": body.operator_id}
