"""
backend/modules/investigation_service.py
────────────────────────────────────────
Orchestrates automatic case analysis and assembles the case-level views
(clues, correlations, map, clue graph) that the Investigation page and the
report are built from.

Flow:  evidence file ──auto_analysis──▶ clues + auto detections
                     ──correlation_engine──▶ cross-evidence matches
                     ──▶ map / graph / report

Nothing here asserts guilt or identity. Automatic output is stored as
unverified observations and is labelled as such everywhere it is shown.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi.concurrency import run_in_threadpool

from backend.modules import audit_engine, auto_analysis
from backend.modules.clue_terms import extract_terms
from backend.modules.clue_text import extract_clues, normalize
from backend.modules.correlation_engine import correlate
from backend.modules.plate_postprocess import parse_plate
from backend.modules.vision.cv_engine import format_timestamp
from backend.modules.vision.objective_lexicon import enforce_objective_lexicon

logger = logging.getLogger(__name__)

AUTO_CLUE_SOURCES = ("AUTO_YOLO", "AUTO_OCR", "DOCUMENT", "TRANSCRIPT")

# Live progress for in-flight analyses (read by the status endpoint).
_PROGRESS: Dict[str, Dict[str, Any]] = {}


def _uid() -> str:
    return uuid.uuid4().hex


def _fmt_ts(ms: Optional[int]) -> str:
    return format_timestamp(int(ms or 0))


# ── persistence helpers ──────────────────────────────────────────────────────

async def _insert_clue(db, case_id, evidence_id, kind, value, norm, conf, source,
                       ts_ms=None, bbox=None, context=None, clue_id=None) -> None:
    await db.execute(
        """INSERT INTO clues
           (id, case_id, evidence_id, kind, value, norm_value, confidence, source,
            timestamp_ms, bbox, context)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (clue_id or _uid(), case_id, evidence_id, kind, str(value)[:500], str(norm)[:500], float(conf),
         source, ts_ms, json.dumps(bbox) if bbox else None, (context or "")[:1000] or None),
    )


def _fix_plate(kind: str, value: str, norm: str, context: str):
    """Format-correct a PLATE reading (O/0, B/8 ...) and note the original read."""
    if kind != "PLATE":
        return value, norm, context
    p = parse_plate(norm)
    if p.pattern == "RAW" or p.text == norm:
        return value, norm, context
    note = f"{context} [format-corrected from read '{norm}', {p.edits} edit(s)]"
    return p.text, p.text, note


def _text_clues_from_sightings(texts) -> List[Dict[str, Any]]:
    """Group OCR sightings per frame, extract clues, aggregate across frames."""
    by_frame: Dict[tuple, list] = {}
    for t in texts:
        by_frame.setdefault((t.frame, t.from_vehicle), []).append(t)

    agg: Dict[tuple, Dict[str, Any]] = {}
    for (_frame, _veh), group in by_frame.items():
        # Individual lines AND the joined string (plates are often split across lines).
        candidates = [(t.text, t.conf, t) for t in group]
        joined = " ".join(t.text for t in group)
        if len(group) > 1:
            candidates.append((joined, sum(t.conf for t in group) / len(group), group[0]))
        for text, conf, src in candidates:
            for c in extract_clues(text):
                key = (c.kind, c.norm)
                cur = agg.get(key)
                if cur is None:
                    agg[key] = {"kind": c.kind, "value": c.value, "norm": c.norm,
                                "conf": conf, "ts_ms": src.ts_ms, "bbox": src.bbox_rel,
                                "context": c.context, "count": 1}
                else:
                    cur["count"] += 1
                    if conf > cur["conf"]:
                        cur.update(conf=conf, value=c.value, bbox=src.bbox_rel, context=c.context)
                    cur["ts_ms"] = min(cur["ts_ms"], src.ts_ms)
    return list(agg.values())


async def analyze_evidence(evidence_id: str) -> Dict[str, Any]:
    """Run the full automatic pipeline for one evidence item and persist results."""
    from backend.database.db import get_db

    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM evidence WHERE id = %s", (evidence_id,))
        ev = await cur.fetchone()
        await db.commit()
    finally:
        await db.close()
    if not ev:
        raise ValueError("Evidence not found")
    ev = dict(ev)
    case_id, ftype, path = ev["case_id"], ev["file_type"], ev["file_path"]

    _PROGRESS[evidence_id] = {"status": "RUNNING", "progress": 0}
    await _set_status(evidence_id, "RUNNING", "Analysis started", 0)

    def on_progress(done: int, total: int) -> None:
        _PROGRESS[evidence_id] = {"status": "RUNNING", "progress": int(100 * done / max(1, total))}

    try:
        result = None
        if ftype == "VIDEO":
            result = await run_in_threadpool(auto_analysis.analyze_video, path, on_progress)
        elif ftype == "IMAGE":
            result = await run_in_threadpool(auto_analysis.analyze_image, path)
        elif ftype == "DOCUMENT" and str(path).lower().endswith(".pdf"):
            result = await run_in_threadpool(auto_analysis.analyze_pdf, path)

        counts = await _persist(ev, result)
        warnings = list(result.warnings) if result else []
        status = "PARTIAL" if warnings else "COMPLETED"
        msg = "; ".join(warnings) or "Analysis complete"
        await _set_status(evidence_id, status, msg, 100)
        _PROGRESS[evidence_id] = {"status": status, "progress": 100}

        await audit_engine.append_entry(
            "AUTO_ANALYSIS_COMPLETED", operator_id="SYSTEM", case_id=case_id,
            evidence_id=evidence_id, file_hash_sha256=ev.get("file_hash_sha256"),
            metadata={**counts, "status": status, "warnings": warnings,
                      "detector": auto_analysis.capabilities()["detector_model"],
                      "frames_analyzed": getattr(result, "frames_analyzed", 0)},
        )
        return {"evidence_id": evidence_id, "status": status, **counts}
    except Exception as exc:
        logger.exception("Automatic analysis failed for %s", evidence_id)
        await _set_status(evidence_id, "FAILED", str(exc)[:500], 0)
        _PROGRESS[evidence_id] = {"status": "FAILED", "progress": 0}
        return {"evidence_id": evidence_id, "status": "FAILED", "error": str(exc)}


async def _set_status(evidence_id: str, status: str, message: str, progress: int) -> None:
    from backend.database.db import get_db
    db = await get_db()
    try:
        await db.execute(
            "UPDATE evidence SET analysis_status=%s, analysis_message=%s, analysis_progress=%s WHERE id=%s",
            (status, message[:1000], progress, evidence_id),
        )
        await db.commit()
    finally:
        await db.close()


async def _persist(ev: Dict[str, Any], result) -> Dict[str, int]:
    from backend.database.db import get_db

    evidence_id, case_id = ev["id"], ev["case_id"]
    counts = {"objects": 0, "text_clues": 0, "transcript_clues": 0, "document_pages": 0}

    db = await get_db()
    try:
        # Idempotent re-runs: wipe previous automatic output for this evidence.
        await db.execute(
            "DELETE FROM clues WHERE evidence_id=%s AND source IN ('AUTO_YOLO','AUTO_OCR','DOCUMENT','TRANSCRIPT')",
            (evidence_id,))
        await db.execute("DELETE FROM detections WHERE evidence_id=%s AND source='AUTO_YOLO'", (evidence_id,))

        if result is not None:
            # Tracking pipeline: one detection + one clue per tracked object,
            # one PLATE clue per voted plate.
            for tr in result.tracks:
                det_id = _uid()
                cls_label = auto_analysis.objective_class_label(tr.cls)
                label, _ = enforce_objective_lexicon(f"{tr.color} {cls_label}".strip()
                                                     if tr.color != "unknown" else cls_label)
                details = [f"tracked across {tr.frames} detection frame(s)",
                           f"from {_fmt_ts(tr.first_ms)} to {_fmt_ts(tr.last_ms)}",
                           f"detector: {tr.source}"]
                if tr.plate:
                    details.append(f"plate read: {tr.plate}")
                await db.execute(
                    """INSERT INTO detections
                       (id, evidence_id, label, confidence, bounding_box, frame_timestamp,
                        source, category, readout_text, details_json, lexicon_compliant,
                        frame_index, timestamp_str, operator_id, verification_status,
                        class_name, track_key)
                       VALUES (%s,%s,%s,%s,%s,%s,'AUTO_YOLO',%s,%s,%s,1,%s,%s,'AUTO','Unverified_Draft',%s,%s)""",
                    (det_id, evidence_id, label, tr.max_conf, json.dumps(tr.best_bbox_rel),
                     tr.first_ms / 1000.0, auto_analysis.category_for(tr.cls), tr.plate or "NONE",
                     json.dumps(details[:3]), tr.best_frame, _fmt_ts(tr.first_ms), tr.cls, tr.key),
                )
                await _insert_clue(db, case_id, evidence_id, "OBJECT", label, label.lower(),
                                   tr.max_conf, "AUTO_YOLO", tr.first_ms, tr.best_bbox_rel,
                                   f"{tr.cls} tracked for {tr.frames} frame(s), "
                                   f"{_fmt_ts(tr.first_ms)}-{_fmt_ts(tr.last_ms)}", clue_id=det_id)
                counts["objects"] += 1

            for pl in result.plates:
                reads = ", ".join(f"{t}({c:.2f})" for t, c in pl.reads[:6])
                note = (f"voted from {pl.n_reads} read(s), agreement {pl.agreement:.0%}"
                        + (f", {pl.edits} format correction(s)" if pl.edits else "")
                        + (", state code NOT recognised" if pl.state_valid is False else "")
                        + f"; reads: {reads}")
                await _insert_clue(db, case_id, evidence_id, "PLATE", pl.text, pl.text,
                                   pl.confidence, "AUTO_OCR", pl.first_ms, pl.bbox_rel, note)
                counts["text_clues"] += 1

            # Objects → unverified detections + appearance clues
            for seg in (result.segments if not result.tracks else []):
                label, _ = enforce_objective_lexicon(f"{seg.color} {seg.cls}".strip())
                await db.execute(
                    """INSERT INTO detections
                       (id, evidence_id, label, confidence, bounding_box, frame_timestamp,
                        source, category, readout_text, details_json, lexicon_compliant,
                        frame_index, timestamp_str, operator_id, verification_status)
                       VALUES (%s,%s,%s,%s,%s,%s,'AUTO_YOLO',%s,'NONE',%s,1,%s,%s,'AUTO','Unverified_Draft')""",
                    (_uid(), evidence_id, label, seg.max_conf, json.dumps(seg.best_bbox_rel),
                     seg.first_ms / 1000.0, auto_analysis.category_for(seg.cls),
                     json.dumps([f"seen in {seg.count} sampled frame(s)",
                                 f"from {_fmt_ts(seg.first_ms)} to {_fmt_ts(seg.last_ms)}"]),
                     seg.best_frame, _fmt_ts(seg.first_ms)),
                )
                is_still = result.kind == "IMAGE"   # stills have no timeline position
                await _insert_clue(db, case_id, evidence_id, "OBJECT", label, label.lower(),
                                   seg.max_conf, "AUTO_YOLO", None if is_still else seg.first_ms,
                                   seg.best_bbox_rel,
                                   f"{seg.cls} detected in {seg.count} sampled frame(s)")
                counts["objects"] += 1

            voted = result.method == "tracking+voting"
            for c in _text_clues_from_sightings(result.texts):
                c["value"], c["norm"], c["context"] = _fix_plate(c["kind"], c["value"], c["norm"], c["context"])
                if voted and c["kind"] == "PLATE":
                    continue   # plates come from the consolidated, voted readings
                await _insert_clue(db, case_id, evidence_id, c["kind"], c["value"], c["norm"],
                                   c["conf"], "AUTO_OCR",
                                   None if result.kind == "IMAGE" else c["ts_ms"], c["bbox"],
                                   f"{c['context']} (read {c['count']}x)")
                counts["text_clues"] += 1

            # PDF text -> chunks only; clues are derived live from chunks at read time,
            # so they always reflect the current text (and later edits/transcripts).
            if result.pages:
                await db.execute(
                    "DELETE FROM text_chunks WHERE evidence_id=%s AND source_type IN ('PDF','PDF_OCR')",
                    (evidence_id,))
                for i, (page_no, text) in enumerate(result.pages):
                    stype = "PDF_OCR" if page_no in getattr(result, "ocr_pages", set()) else "PDF"
                    await db.execute(
                        """INSERT INTO text_chunks (id, evidence_id, chunk_index, content, source_type, page_number)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        (_uid(), evidence_id, i, text[:20000], stype, page_no))
                    counts["document_pages"] += 1

            # EXIF location / capture time (never overwrite a manually set location)
            if result.exif:
                ex = result.exif
                await db.execute(
                    """UPDATE evidence SET
                         latitude = COALESCE(latitude, %s), longitude = COALESCE(longitude, %s),
                         location_label = COALESCE(location_label, %s),
                         captured_at = COALESCE(captured_at, %s)
                       WHERE id = %s""",
                    (ex.get("latitude"), ex.get("longitude"),
                     "EXIF GPS" if ex.get("latitude") is not None else None,
                     ex.get("captured_at"), evidence_id))

        await db.commit()
    except Exception:
        await db.conn.rollback()
        raise
    finally:
        await db.close()
    return counts


def get_progress(evidence_id: str) -> Optional[Dict[str, Any]]:
    return _PROGRESS.get(evidence_id)


async def analyze_case(case_id: str) -> List[Dict[str, Any]]:
    """Sequentially analyse every evidence item in a case (CPU-friendly)."""
    from backend.database.db import get_db
    db = await get_db()
    try:
        cur = await db.execute("SELECT id FROM evidence WHERE case_id=%s ORDER BY uploaded_at", (case_id,))
        ids = [r["id"] for r in await cur.fetchall()]
        await db.commit()
    finally:
        await db.close()
    out = []
    for eid in ids:
        out.append(await analyze_evidence(eid))
    return out


# ── case-level read models ───────────────────────────────────────────────────

async def load_case_context(case_id: str) -> Dict[str, Any]:
    """Case row, evidence rows, clues (incl. VLM ROI findings) and detections."""
    from backend.database.db import get_db

    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM cases WHERE id=%s", (case_id,))
        case = await cur.fetchone()
        if not case:
            return {}
        cur = await db.execute("SELECT * FROM evidence WHERE case_id=%s ORDER BY uploaded_at", (case_id,))
        evidence = [dict(r) for r in await cur.fetchall()]
        cur = await db.execute("SELECT * FROM clues WHERE case_id=%s", (case_id,))
        clues = [dict(r) for r in await cur.fetchall()]
        cur = await db.execute(
            """SELECT d.* FROM detections d JOIN evidence e ON e.id=d.evidence_id
               WHERE e.case_id=%s ORDER BY d.evidence_id, d.frame_timestamp""", (case_id,))
        detections = [dict(r) for r in await cur.fetchall()]
        cur = await db.execute(
            """SELECT t.id, t.evidence_id, t.chunk_index, t.content, t.source_type, t.page_number,
                      t.start_time, t.end_time
               FROM text_chunks t JOIN evidence e ON e.id=t.evidence_id
               WHERE e.case_id=%s ORDER BY t.evidence_id, t.chunk_index""", (case_id,))
        chunks = [dict(r) for r in await cur.fetchall()]
        await db.commit()
    finally:
        await db.close()
    return {"case": dict(case), "evidence": evidence, "clues": clues,
            "detections": detections, "chunks": chunks}


def _chunk_source(source_type: Optional[str]) -> str:
    return "DOCUMENT" if str(source_type or "").upper().startswith("PDF") else "TRANSCRIPT"


def chunk_terms(content: str):
    """Every clue (patterns + names + object phrases) found in one text chunk."""
    return extract_clues(content or "") + extract_terms(content or "")


def _clue_dicts(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    The complete clue pool for a case, normalised for the correlation engine:

      * persisted clues from automatic analysis (objects, OCR, plates, EXIF)
      * clues derived LIVE from every text chunk (speech transcripts, PDF text,
        PDF OCR) — derived at read time so a transcript created after analysis
        is still picked up and nothing goes stale
      * clues derived LIVE from operator regional scans (label, readout, notes)
    """
    out: List[Dict[str, Any]] = []

    # 1. persisted clues (transcript/document ones are re-derived live below)
    for c in ctx["clues"]:
        if c["source"] in ("TRANSCRIPT", "DOCUMENT"):
            continue
        bbox = None
        if c.get("bbox"):
            try:
                bbox = json.loads(c["bbox"])
            except (TypeError, json.JSONDecodeError):
                bbox = None
        out.append({"id": c["id"], "evidence_id": c["evidence_id"], "kind": c["kind"],
                    "value": c["value"], "norm_value": c["norm_value"],
                    "confidence": c["confidence"], "source": c["source"],
                    "timestamp_ms": c["timestamp_ms"], "context": c["context"],
                    "bbox": bbox, "verified": False})

    # 2. text chunks -> clues (one clue per evidence/kind/value, earliest occurrence)
    seen: Dict[tuple, Dict[str, Any]] = {}
    for ch in ctx.get("chunks", []):
        source = _chunk_source(ch.get("source_type"))
        ts = int(float(ch["start_time"]) * 1000) if ch.get("start_time") is not None else None
        where = f"page {ch['page_number']}: " if ch.get("page_number") else ""
        for c in chunk_terms(ch.get("content") or ""):
            value, norm, context = _fix_plate(c.kind, c.value, c.norm, c.context)
            key = (ch["evidence_id"], c.kind, norm)
            if key in seen:
                seen[key]["_n"] += 1
                continue
            d = {"id": f"chunk:{ch['id']}:{c.kind}:{norm}"[:190], "evidence_id": ch["evidence_id"],
                 "kind": c.kind, "value": value, "norm_value": norm,
                 "confidence": 0.9 if source == "DOCUMENT" else 0.6, "source": source,
                 "timestamp_ms": ts, "context": where + context, "bbox": None,
                 "verified": False, "chunk_id": ch["id"], "_n": 1}
            seen[key] = d
            out.append(d)
    for d in seen.values():
        n = d.pop("_n", 1)
        if n > 1:
            d["context"] = f"{d['context']} (mentioned {n}x)"

    # 3. operator regional scans -> clues
    for d in ctx["detections"]:
        if d.get("source") != "VLM_ROI":
            continue
        verified = d.get("verification_status") == "Verified"
        ts = int(float(d.get("frame_timestamp") or 0) * 1000)
        conf = float(d.get("confidence") or 0)
        base = {"evidence_id": d["evidence_id"], "confidence": conf, "source": "VLM_ROI",
                "timestamp_ms": ts, "bbox": None, "verified": verified}
        label = (d.get("label") or "").strip()
        readout = (d.get("readout_text") or "").strip()
        try:
            details = [str(x) for x in json.loads(d.get("details_json") or "[]")]
        except (TypeError, json.JSONDecodeError):
            details = []
        note = f"Operator-selected region analysed by local VLM: {label}"

        # the described object itself (people are never matched on appearance)
        if label and d.get("category") != "PERSON":
            out.append({**base, "id": f"roi:{d['id']}:obj", "kind": "OBJECT", "value": label,
                        "norm_value": label.lower(), "context": note})

        # visible text: patterns first, otherwise keep the readout itself as a TEXT clue
        if readout and readout.upper() != "NONE":
            pattern = extract_clues(readout)
            for c in pattern:
                v, n, ctx_note = _fix_plate(c.kind, c.value, c.norm, f"ROI readout: {readout}")
                out.append({**base, "id": f"roi:{d['id']}:{c.kind}:{n}", "kind": c.kind, "value": v,
                            "norm_value": n, "context": ctx_note})
            alnum = re.sub(r"[^A-Z0-9]", "", readout.upper())
            if not pattern and len(alnum) >= 4:
                out.append({**base, "id": f"roi:{d['id']}:text:{alnum}", "kind": "TEXT",
                            "value": readout, "norm_value": alnum, "context": f"ROI readout: {readout}"})

        # Names / object phrases in the model's notes. The label is already an
        # OBJECT clue above, so from the label only NAMES are taken (no duplicate).
        terms = [c for c in extract_terms(label) if c.kind == "NAME"]
        terms += extract_terms(" . ".join(details))
        seen_terms = set()
        for c in terms:
            if (c.kind, c.norm) in seen_terms:
                continue
            seen_terms.add((c.kind, c.norm))
            out.append({**base, "id": f"roi:{d['id']}:{c.kind}:{c.norm}", "kind": c.kind,
                        "value": c.value, "norm_value": c.norm,
                        "context": f"Regional scan note: {c.context}"})

    # de-duplicate ids, drop person-appearance objects
    uniq: Dict[str, Dict[str, Any]] = {}
    for c in out:
        uniq.setdefault(c["id"], c)
    return [c for c in uniq.values()
            if not (c["kind"] == "OBJECT" and "person" in (c["norm_value"] or "").split())]


async def case_correlations(case_id: str) -> Dict[str, Any]:
    ctx = await load_case_context(case_id)
    if not ctx:
        return {}
    evidence = {e["id"]: e for e in ctx["evidence"]}
    clues = _clue_dicts(ctx)
    matches = correlate(clues, evidence)
    return {"ctx": ctx, "clues": clues, "matches": matches, "evidence": evidence}


def build_clue_graph(matches: List[Dict[str, Any]], evidence: Dict[str, Dict[str, Any]],
                     include_weak: bool = False) -> Dict[str, Any]:
    """Evidence ↔ matched-clue graph in Cytoscape element format."""
    nodes, edges, used = [], [], set()
    type_for = {"PLATE": "Vehicle", "OBJECT": "Item"}
    for m in matches:
        if m["strength"] == "WEAK" and not include_weak:
            continue
        nid = f"clue:{m['id']}"
        nodes.append({"data": {
            "id": nid, "label": m["value"], "node_type": type_for.get(m["kind"], "Text"),
            "readout": m["value"], "confidence": m["score"],
            "finding_ids": [x["clue_id"] for x in m["members"]], "evidence_ids": m["evidence_ids"],
            "first_seen": None, "strength": m["strength"],
        }})
        for member in m["members"]:
            used.add(member["evidence_id"])
            eid = f"{m['id']}:{member['evidence_id']}:{member['clue_id']}"[:200]
            edges.append({"data": {
                "id": eid, "source": nid, "target": f"ev:{member['evidence_id']}",
                "relation": "appears_in", "label": member["timestamp_str"] or "appears in",
                "reason": f"{m['explanation']} ({member['source']}, {member['timestamp_str'] or 'whole file'})",
                "source_refs": [member["clue_id"]],
            }})
    for ev_id in sorted(used):
        info = evidence.get(ev_id, {})
        nodes.append({"data": {"id": f"ev:{ev_id}", "label": info.get("file_name", ev_id),
                               "node_type": "Evidence", "finding_ids": [], "evidence_ids": [ev_id],
                               "confidence": None}})
    return {"nodes": nodes, "edges": edges,
            "meta": {"finding_count": len(matches), "window_s": 0,
                     "note": "Clues shared between evidence items. Links are observational, not assertions of identity or involvement."}}


def build_map(ctx: Dict[str, Any], matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    points, unlocated = [], []
    match_by_ev: Dict[str, List[str]] = {}
    for m in matches:
        if m["strength"] == "WEAK":
            continue
        for ev_id in m["evidence_ids"]:
            match_by_ev.setdefault(ev_id, []).append(m["id"])

    for e in ctx["evidence"]:
        item = {"evidence_id": e["id"], "file_name": e["file_name"], "file_type": e["file_type"],
                "latitude": e.get("latitude"), "longitude": e.get("longitude"),
                "label": e.get("location_label"), "captured_at": e.get("captured_at"),
                "match_ids": match_by_ev.get(e["id"], [])}
        if e.get("latitude") is not None and e.get("longitude") is not None:
            points.append(item)
        else:
            unlocated.append(item)

    links, seen = [], set()
    for m in matches:
        if m["strength"] == "WEAK":
            continue
        ids = [i for i in m["evidence_ids"] if any(p["evidence_id"] == i for p in points)]
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                key = (a, b, m["id"])
                if key not in seen:
                    seen.add(key)
                    links.append({"from": a, "to": b, "match_id": m["id"], "value": m["value"],
                                  "kind": m["kind"], "strength": m["strength"]})
    return {"points": points, "unlocated": unlocated, "links": links}
