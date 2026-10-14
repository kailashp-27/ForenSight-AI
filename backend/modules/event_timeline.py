"""
backend/modules/event_timeline.py
─────────────────────────────────
Builds a single wall-clock timeline of what happened, across evidence types:

  chat message            (its own timestamp)
  time mentioned in text  ("maintenance window at 1:00 AM")
  speech segment          (recording start + offset, when the start is known)
  regional scan / frame   (video recording start + frame offset)

then finds ALIGNMENTS: events that sit close in time and share something
concrete (a location such as "Sector 4", a name, a vehicle, an item, a plate).
Events whose time is unknown are not dropped: they are attached to a dated
group when they share a location / person / item with it, and are labelled as
linked by content only.

Honesty rules (also shown in the UI):
  * a time-of-day with no date is placed on the most common known date and
    flagged `assumed_date`;
  * a time that is only MENTIONED is a reference, not an observation, and is
    marked as such;
  * nothing here asserts causation, only proximity and shared terms.

Pure functions over plain dicts.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.modules.clock import add_offset, to_datetime

LINK_KINDS = {"LOCATION", "NAME", "OBJECT", "PLATE", "ID", "TEXT"}
# An event with no clock time is attached to a dated group only through something specific.
# A vehicle/item description ("white van") is too common to justify placing it in time.
JOIN_KINDS = {"LOCATION", "NAME", "PLATE", "ID"}


def _short(text: str, n: int = 160) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def _term_dicts(clues) -> List[Dict[str, str]]:
    seen, out = set(), []
    for c in clues:
        key = (c.kind, c.norm)
        if key in seen or c.kind not in LINK_KINDS | {"TIME"}:
            continue
        seen.add(key)
        out.append({"kind": c.kind, "value": c.value, "norm": c.norm})
    return out


def build_event_timeline(
    ctx: Dict[str, Any],
    chunk_terms: Callable[[str], list],
    window_min: int = 45,
) -> Dict[str, Any]:
    evidence = {e["id"]: e for e in ctx["evidence"]}
    chunks = ctx.get("chunks", [])

    # ── known dates -> the date undated clock times are assumed to fall on ───
    known_dates: List[str] = []
    for ch in chunks:
        wt = ch.get("wall_time") or ""
        if re.match(r"^\d{4}-\d{2}-\d{2}T", wt):
            known_dates.append(wt[:10])
    for e in evidence.values():
        for key in ("recording_start", "captured_at"):
            v = e.get(key) or ""
            if re.match(r"^\d{4}-\d{2}-\d{2}", v):
                known_dates.append(v[:10])
    assumed_date = Counter(known_dates).most_common(1)[0][0] if known_dates else None

    events: List[Dict[str, Any]] = []

    def add(ev_id: str, kind: str, label: str, text: str, when: Optional[datetime], date_known: bool,
            terms: List[Dict[str, str]], observed: bool, offset_ms: Optional[int] = None,
            ref: Optional[str] = None) -> None:
        events.append({
            "id": f"ev{len(events)}", "evidence_id": ev_id,
            "file_name": evidence.get(ev_id, {}).get("file_name", ev_id),
            "file_type": evidence.get(ev_id, {}).get("file_type"),
            "kind": kind, "label": label, "text": _short(text),
            "time": when.strftime("%Y-%m-%dT%H:%M:%S") if when else None,
            "date_known": bool(date_known and when is not None),
            "assumed_date": bool(when is not None and not date_known),
            "observed": observed, "offset_ms": offset_ms, "ref": ref, "terms": terms,
        })

    # ── 1. chat messages + times mentioned anywhere in text ─────────────────
    for ch in chunks:
        ev_id = ch["evidence_id"]
        content = ch.get("content") or ""
        clues = chunk_terms(content)
        terms = _term_dicts(clues)
        src = str(ch.get("source_type") or "").upper()
        base_start = evidence.get(ev_id, {}).get("recording_start")

        when, known = None, False
        if src == "CHAT" and ch.get("wall_time"):
            parsed = to_datetime(ch["wall_time"], assumed_date)
            if parsed:
                when, known = parsed
        elif ch.get("start_time") is not None and base_start:
            parsed = add_offset(base_start, float(ch["start_time"]), assumed_date)
            if parsed:
                when, known = parsed

        if src == "CHAT":
            spk = ch.get("speaker") or "message"
            add(ev_id, "message", f"{spk}", content, when, known, terms, observed=True, ref=ch["id"])
        elif ch.get("start_time") is not None:
            off = int(float(ch["start_time"]) * 1000)
            add(ev_id, "speech", "Speech", content, when, known, terms, observed=True, offset_ms=off, ref=ch["id"])
        elif src.startswith("PDF"):
            add(ev_id, "document", f"Document text{(' p.' + str(ch['page_number'])) if ch.get('page_number') else ''}",
                content, None, False, terms, observed=True, ref=ch["id"])

        # a clock time written in the text is an event in itself (a reference)
        for t in (c for c in clues if c.kind == "TIME"):
            parsed = to_datetime(t.norm, assumed_date)
            if src == "CHAT" and when is not None and known:
                parsed = (datetime.combine(when.date(), parsed[0].time()), True) if parsed else None
            if parsed:
                add(ev_id, "mention", f"Refers to {t.value}", t.context or content, parsed[0], parsed[1],
                    terms, observed=False, ref=ch["id"])

    # ── 2. regional scans placed on the video's clock ───────────────────────
    for ev in ctx["evidence"]:
        if ev["file_type"] == "VIDEO" and ev.get("recording_start"):
            parsed = to_datetime(ev["recording_start"], assumed_date)
            if parsed:
                add(ev["id"], "video", "Recording starts (burned-in clock)", ev["file_name"], parsed[0], parsed[1],
                    [], observed=True)
    for d in ctx["detections"]:
        if d.get("source") != "VLM_ROI":
            continue
        ev = evidence.get(d["evidence_id"], {})
        start = ev.get("recording_start")
        when, known = None, False
        if start:
            parsed = add_offset(start, float(d.get("frame_timestamp") or 0), assumed_date)
            if parsed:
                when, known = parsed
        readout = d.get("readout_text") or ""
        text = f"{d.get('label')}" + (f" — reads '{readout}'" if readout and readout.upper() != "NONE" else "")
        terms = _term_dicts(chunk_terms(f"{d.get('label')}. {readout if readout.upper() != 'NONE' else ''}"))
        add(d["evidence_id"], "scan", f"Frame {d.get('timestamp_str') or ''}".strip(), text, when, known, terms,
            observed=True, offset_ms=int(float(d.get("frame_timestamp") or 0) * 1000), ref=d["id"])

    # ── 3. order ────────────────────────────────────────────────────────────
    dated = [e for e in events if e["time"]]
    undated = [e for e in events if not e["time"]]
    dated.sort(key=lambda e: e["time"])

    # ── 4. alignment groups ─────────────────────────────────────────────────
    window = timedelta(minutes=window_min)
    clusters: List[List[Dict[str, Any]]] = []
    for e in dated:
        t = datetime.strptime(e["time"], "%Y-%m-%dT%H:%M:%S")
        if clusters and t - datetime.strptime(clusters[-1][-1]["time"], "%Y-%m-%dT%H:%M:%S") <= window:
            clusters[-1].append(e)
        else:
            clusters.append([e])

    def term_keys(e: Dict[str, Any], kinds=LINK_KINDS) -> set:
        return {(t["kind"], t["norm"]) for t in e["terms"] if t["kind"] in kinds}

    groups = []
    for cl in clusters:
        ev_ids = {e["evidence_id"] for e in cl}
        # undated events join when they share a concrete term with a member
        member_terms = set().union(*(term_keys(e, JOIN_KINDS) for e in cl)) if cl else set()
        joined = [u for u in undated if term_keys(u, JOIN_KINDS) & member_terms]
        all_ev = ev_ids | {u["evidence_id"] for u in joined}
        if len(all_ev) < 2:
            continue
        # shared terms = present in events of at least two different evidence items
        by_term: Dict[tuple, set] = defaultdict(set)
        label_for: Dict[tuple, str] = {}
        for e in cl + joined:
            for t in e["terms"]:
                if t["kind"] in LINK_KINDS:
                    by_term[(t["kind"], t["norm"])].add(e["evidence_id"])
                    label_for.setdefault((t["kind"], t["norm"]), t["value"])
        shared = [{"kind": k[0], "value": label_for[k]} for k, v in by_term.items() if len(v) >= 2]
        times = [e["time"] for e in cl]
        groups.append({
            "id": f"g{len(groups)}",
            "start": min(times), "end": max(times),
            "evidence_ids": sorted(all_ev),
            "file_names": sorted({evidence[i]["file_name"] for i in all_ev if i in evidence}),
            "event_ids": [e["id"] for e in cl],
            "linked_undated_ids": [u["id"] for u in joined],
            "shared_terms": shared,
            "assumed_date": any(e["assumed_date"] for e in cl),
            "summary": (f"{len(cl) + len(joined)} item(s) from {len(all_ev)} evidence files between "
                        f"{min(times)[11:16]} and {max(times)[11:16]}"
                        + (f"; shared: {', '.join(s['value'] for s in shared[:5])}" if shared else "")),
        })

    return {
        "events": dated + undated,
        "groups": groups,
        "assumed_date": assumed_date,
        "stats": {"dated": len(dated), "undated": len(undated), "groups": len(groups),
                  "assumed_date_events": sum(1 for e in dated if e["assumed_date"])},
        "notes": [
            "Events whose date could not be read are placed on the most common date in the case and marked as assumed."
            if assumed_date else
            "No dated evidence was found; times are shown as time-of-day on an arbitrary day.",
            "A 'refers to' event is a time that someone wrote or said, not a recorded observation.",
        ],
    }
