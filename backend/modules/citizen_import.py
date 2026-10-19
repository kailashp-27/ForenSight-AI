"""
backend/modules/citizen_import.py
─────────────────────────────────
Loads the citizen register (a spreadsheet of FICTIONAL people used as the
reference database) into the `citizens` table.

Columns: ID, Full Name, Date of Birth, Phone Number, Address, Occupation,
         Criminal Record, Status.

Idempotent: re-running updates existing IDs and adds new ones; it never
deletes rows or touches the photo / case links of a citizen.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SEED_PATH = Path(__file__).resolve().parents[1] / "seed" / "citizens.xlsx"

_HEADERS = {
    "id": "id", "full name": "full_name", "name": "full_name", "date of birth": "dob", "dob": "dob",
    "phone number": "phone", "phone": "phone", "address": "address", "occupation": "occupation",
    "criminal record": "criminal_record", "status": "status",
}


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower().replace("-", " ")).strip()


def digits(s: Any) -> str:
    return re.sub(r"\D", "", str(s or ""))


def _clean(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s or None


def read_rows(path: str | Path) -> List[Dict[str, Any]]:
    """Parse the workbook into dicts (pure; no database)."""
    import openpyxl

    ws = openpyxl.load_workbook(str(path), data_only=True).worksheets[0]
    it = ws.iter_rows(values_only=True)
    header = [_HEADERS.get(str(h or "").strip().lower()) for h in next(it)]
    if "id" not in header or "full_name" not in header:
        raise ValueError("The sheet needs at least 'ID' and 'Full Name' columns")

    rows: List[Dict[str, Any]] = []
    for raw in it:
        rec = {k: v for k, v in zip(header, raw) if k}
        try:
            cid = int(float(rec["id"]))
        except (TypeError, ValueError):
            continue
        name = _clean(rec.get("full_name"))
        if not name:
            continue
        dob = rec.get("dob")
        if isinstance(dob, datetime):
            dob = dob.date()
        elif not isinstance(dob, date):
            dob = None
        phone = _clean(rec.get("phone"))
        rows.append({
            "id": cid, "full_name": name, "norm_name": norm_name(name), "dob": dob,
            "phone": phone, "phone_digits": digits(phone)[-15:] if phone else None,
            "address": _clean(rec.get("address")), "occupation": _clean(rec.get("occupation")),
            "criminal_record": _clean(rec.get("criminal_record")) or "None",
            "status": _clean(rec.get("status")) or "Unknown",
        })
    return rows


async def import_rows(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    from backend.database.db import get_db

    added = updated = 0
    db = await get_db()
    try:
        for r in rows:
            cur = await db.execute("SELECT id FROM citizens WHERE id=%s", (r["id"],))
            exists = await cur.fetchone()
            vals = (r["full_name"], r["norm_name"], r["dob"], r["phone"], r["phone_digits"], r["address"],
                    r["occupation"], r["criminal_record"], r["status"])
            if exists:
                await db.execute(
                    """UPDATE citizens SET full_name=%s, norm_name=%s, dob=%s, phone=%s, phone_digits=%s,
                       address=%s, occupation=%s, criminal_record=%s, status=%s WHERE id=%s""",
                    vals + (r["id"],))
                updated += 1
            else:
                await db.execute(
                    """INSERT INTO citizens (full_name, norm_name, dob, phone, phone_digits, address, occupation,
                       criminal_record, status, id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    vals + (r["id"],))
                added += 1
        await db.commit()
    except Exception:
        await db.conn.rollback()
        raise
    finally:
        await db.close()
    return {"added": added, "updated": updated, "total": len(rows)}


async def import_xlsx(path: str | Path = SEED_PATH) -> Dict[str, int]:
    return await import_rows(read_rows(path))


async def seed_if_empty() -> None:
    """On first start, load the bundled (fictional) register so the Citizens page is never empty."""
    from backend.database.db import get_db

    if not SEED_PATH.exists():
        return
    db = await get_db()
    try:
        cur = await db.execute("SELECT COUNT(*) AS n FROM citizens")
        n = list((await cur.fetchone()).values())[0]
        await db.commit()
    finally:
        await db.close()
    if int(n) == 0:
        try:
            result = await import_xlsx(SEED_PATH)
            print(f"[DB] Citizen register seeded: {result}")
        except Exception as exc:       # never block start-up on seed data
            logger.warning("Citizen seed failed: %s", exc)
