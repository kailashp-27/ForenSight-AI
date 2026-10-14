"""
backend/modules/chat_parse.py
─────────────────────────────
Parse chat / message exports (Slack JSON, generic JSON message lists, WhatsApp-
style or "[date time] user: text" plain text) into timestamped messages.

Each message keeps WHO said it and WHEN, because the "when" is what lets the
event timeline line a chat message ("maintenance window at 1:00 AM") up with a
voicemail and a CCTV frame. Pure functions; no I/O.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ChatMessage:
    author: Optional[str]
    text: str
    wall_time: Optional[str]       # ISO "YYYY-MM-DDTHH:MM:SS" or time-of-day "HH:MM" (date unknown)
    date_known: bool = False


_TEXT_KEYS = ("text", "message", "msg", "content", "body")
_AUTHOR_KEYS = ("user_name", "username", "user", "name", "from", "author", "sender", "real_name", "user_profile")
_TIME_KEYS = ("ts", "timestamp", "time", "date", "datetime", "created_at", "sent_at")


def _first(d: Dict[str, Any], keys) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _iso_from_any(v: Any) -> Optional[str]:
    """Epoch seconds (Slack 'ts' like '1760146800.000200') or an ISO-ish string -> ISO UTC."""
    if v is None:
        return None
    try:
        f = float(v)
        if f > 1e11:          # milliseconds
            f /= 1000.0
        if f > 1e8:
            return datetime.fromtimestamp(f, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError):
        pass
    s = str(v).strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M", "%m/%d/%Y %I:%M %p",
                "%d/%m/%Y %I:%M %p", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return None


def _author(v: Any) -> Optional[str]:
    if isinstance(v, dict):
        v = _first(v, ("real_name", "display_name", "name", "username"))
    return str(v).strip() if v not in (None, "") else None


def _walk_json(data: Any) -> List[Dict[str, Any]]:
    """Find the list of message dicts inside typical export shapes."""
    if isinstance(data, list):
        if data and all(isinstance(x, dict) for x in data):
            if any(_first(x, _TEXT_KEYS) for x in data):
                return data
            out: List[Dict[str, Any]] = []
            for x in data:
                out += _walk_json(x)
            return out
        return []
    if isinstance(data, dict):
        for key in ("messages", "chat", "conversation", "items", "data", "history"):
            if key in data:
                found = _walk_json(data[key])
                if found:
                    return found
        out = []
        for v in data.values():
            if isinstance(v, (list, dict)):
                out += _walk_json(v)
        return out
    return []


_LINE_PATTERNS = [
    # [11/10/2026, 1:02 AM] jvance: text      /     11/10/2026 01:02 - jvance: text
    re.compile(r"^\[?(?P<d>\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2})[ ,T]+"
               r"(?P<t>\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?)\]?\s*[-–]?\s*"
               r"(?P<a>[^:\n]{1,40}?):\s*(?P<m>.+)$"),
    # [01:02 AM] jvance: text   /   jvance (1:02 AM): text
    re.compile(r"^\[?(?P<t>\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?)\]?\s+(?P<a>[^:\n]{1,40}?):\s*(?P<m>.+)$"),
    re.compile(r"^(?P<a>[A-Za-z][^:\n(]{0,38}?)\s*\((?P<t>\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?)\)\s*:\s*(?P<m>.+)$"),
]


def _to_hhmmss(t: str) -> Optional[str]:
    t = t.strip().upper().replace(".", "")
    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?$", t)
    if not m:
        return None
    h, mi, s, ap = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0), m.group(4)
    if ap == "PM" and h < 12:
        h += 12
    if ap == "AM" and h == 12:
        h = 0
    if h > 23 or mi > 59:
        return None
    return f"{h:02d}:{mi:02d}:{s:02d}"


def _date_part(d: str) -> Optional[str]:
    if re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        return d
    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$", d)
    if not m:
        return None
    a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000
    day, mon = (a, b) if b <= 12 else (b, a)          # d/m/y, tolerate m/d/y
    try:
        return datetime(y, mon, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_chat(raw: str) -> List[ChatMessage]:
    """Best-effort parse. Always returns at least one message for non-empty text."""
    raw = (raw or "").strip()
    if not raw:
        return []

    # JSON first (Slack exports are a JSON array of message objects).
    if raw[0] in "[{":
        try:
            msgs = _walk_json(json.loads(raw))
        except json.JSONDecodeError:
            msgs = []
        out: List[ChatMessage] = []
        for m in msgs:
            text = _first(m, _TEXT_KEYS)
            if not text:
                continue
            iso = _iso_from_any(_first(m, _TIME_KEYS))
            out.append(ChatMessage(_author(_first(m, _AUTHOR_KEYS)), str(text).strip(), iso, bool(iso)))
        if out:
            return out

    # Plain text lines; continuation lines belong to the previous message.
    out = []
    for line in raw.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        hit = None
        for rx in _LINE_PATTERNS:
            hit = rx.match(line.strip())
            if hit:
                break
        if hit:
            g = hit.groupdict()
            t = _to_hhmmss(g.get("t", "")) if g.get("t") else None
            d = _date_part(g["d"]) if g.get("d") else None
            if d and t:
                wall, known = f"{d}T{t}", True
            elif t:
                wall, known = t[:5], False
            else:
                wall, known = None, False
            out.append(ChatMessage(g["a"].strip(), g["m"].strip(), wall, known))
        elif out:
            out[-1].text += " " + line.strip()
        else:
            out.append(ChatMessage(None, line.strip(), None, False))
    return out
