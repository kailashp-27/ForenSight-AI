"""
backend/modules/clock.py
────────────────────────
Wall-clock reasoning for the event timeline.

CCTV exports usually have a burned-in clock ("2026-10-11  01:34:12 AM  CAM 4").
If several frames read consistently, the clip's real start time can be
recovered:   start = overlay_time - offset_into_clip.   That is what lets a
frame at 00:00:09 of the clip be placed at 01:34 on the same clock as a chat
message or a voicemail.

Everything is explicit about what is known: when no date can be read, times are
returned as time-of-day only and flagged `date_known=False`.
Pure functions; no I/O.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, List, Optional, Tuple

from backend.modules.clue_terms import extract_dates

_HMS = re.compile(r"(?<![\d:.])(\d{1,2}):(\d{2}):(\d{2})\s*([AaPp]\.?[Mm]\.?)?(?![\d])")


@dataclass
class RecordingStart:
    value: str            # "YYYY-MM-DDTHH:MM:SS" if the date was read, else "HH:MM:SS"
    date_known: bool
    evidence_points: int  # how many frames agreed
    spread_s: float


def _sod(h: int, m: int, s: int, ap: Optional[str]) -> Optional[int]:
    ap = (ap or "").lower().replace(".", "")
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if h > 23 or m > 59 or s > 59:
        return None
    return h * 3600 + m * 60 + s


def parse_overlay(text: str) -> Optional[Tuple[Optional[str], int]]:
    """(date ISO or None, seconds-of-day) from one OCR line, if it contains HH:MM:SS."""
    m = _HMS.search(text or "")
    if not m:
        return None
    sod = _sod(int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4))
    if sod is None:
        return None
    dates = extract_dates(text)
    return (dates[0].norm if dates else None, sod)


def derive_recording_start(sightings: Iterable[Tuple[str, int]], tolerance_s: float = 6.0) -> Optional[RecordingStart]:
    """
    sightings: (ocr_text, offset_ms_into_clip). Requires >= 2 frames whose implied
    start agrees within `tolerance_s`; otherwise None (random text such as
    "12:00:00" on a sign must not set the clock).
    """
    est: List[Tuple[Optional[str], float]] = []
    for text, off_ms in sightings:
        ov = parse_overlay(text)
        if ov is None:
            continue
        date, sod = ov
        est.append((date, sod - off_ms / 1000.0))
    if len(est) < 2:
        return None

    # Largest group of mutually consistent estimates (circular day arithmetic).
    day = 86400.0
    best: List[Tuple[Optional[str], float]] = []
    for _d, e in est:
        group = [(d2, e2) for d2, e2 in est if min(abs(e2 - e) % day, day - abs(e2 - e) % day) <= tolerance_s]
        if len(group) > len(best):
            best = group
    if len(best) < 2:
        return None

    secs = [e for _d, e in best]
    base = secs[0]
    rel = [((x - base + day / 2) % day) - day / 2 for x in secs]          # unwrap around the first
    start = (base + statistics.median(rel)) % day
    dates = [d for d, _e in best if d]
    h, rem = divmod(int(round(start)) % 86400, 3600)
    mi, s = divmod(rem, 60)
    if dates:
        d0 = max(set(dates), key=dates.count)
        dt = datetime.strptime(d0, "%Y-%m-%d") + timedelta(seconds=int(round(statistics.median(secs))))
        value, known = dt.strftime("%Y-%m-%dT%H:%M:%S"), True
    else:
        value, known = f"{h:02d}:{mi:02d}:{s:02d}", False
    return RecordingStart(value, known, len(best), round(max(rel) - min(rel), 1))


def to_datetime(value: Optional[str], assumed_date: Optional[str] = None) -> Optional[Tuple[datetime, bool]]:
    """
    ISO or time-of-day string -> (datetime, date_known). Time-only values take
    `assumed_date` (flagged unknown) or 2000-01-01 so they can still be ordered.
    """
    if not value:
        return None
    v = str(value).strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt), True
        except ValueError:
            pass
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(v, fmt).time()
            d = datetime.strptime(assumed_date, "%Y-%m-%d") if assumed_date else datetime(2000, 1, 1)
            return datetime.combine(d.date(), t), False
        except (ValueError, TypeError):
            continue
    return None


def add_offset(start: Optional[str], offset_s: float, assumed_date: Optional[str] = None) -> Optional[Tuple[datetime, bool]]:
    base = to_datetime(start, assumed_date)
    if base is None:
        return None
    dt, known = base
    return dt + timedelta(seconds=float(offset_s or 0)), known
