"""
backend/modules/report_engine.py
────────────────────────────────
Builds the case investigation report as a self-contained HTML document
(print-to-PDF friendly). Pure function over a plain data dict so it can be
tested without a database.

Report rules:
  • Machine output is described, never concluded: all machine-generated text
    passes through the objective-lexicon enforcer.
  • Human-verified findings and unverified machine observations are in
    SEPARATE sections; unverified material is clearly marked.
  • Every claim lists its source (evidence file, timestamp, SHA-256).
  • The report states the system's limits (pre-trained models, not a legal
    determination) and the custody-chain status at generation time.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from backend.modules.vision.objective_lexicon import enforce_objective_lexicon

_E = html.escape


def _t(text: Any) -> str:
    """Escape + enforce objective lexicon for machine-produced text."""
    clean, _ = enforce_objective_lexicon(str(text or ""))
    return _E(clean)


def _ts(ms) -> str:
    if ms is None:
        return "whole file"
    ms = int(ms)
    h, r = divmod(ms, 3_600_000)
    m, r = divmod(r, 60_000)
    s, milli = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{milli:03d}"


def _pct(v) -> str:
    try:
        return f"{round(float(v) * 100)}%"
    except (TypeError, ValueError):
        return "—"


_CSS = """
body{font-family:Segoe UI,Arial,sans-serif;color:#111827;max-width:960px;margin:24px auto;padding:0 20px;line-height:1.5}
h1{font-size:24px;margin-bottom:2px} h2{font-size:17px;border-bottom:2px solid #e5e7eb;padding-bottom:4px;margin-top:28px}
h3{font-size:14px;margin:14px 0 4px} table{border-collapse:collapse;width:100%;font-size:12.5px;margin:8px 0}
th,td{border:1px solid #d1d5db;padding:5px 8px;text-align:left;vertical-align:top} th{background:#f3f4f6}
.mono{font-family:Consolas,monospace;font-size:11.5px;word-break:break-all}
.banner{background:#fffbeb;border:1px solid #f59e0b;padding:10px 12px;border-radius:6px;font-size:13px}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700}
.strong{background:#dcfce7;color:#166534}.medium{background:#fef9c3;color:#854d0e}.weak{background:#e5e7eb;color:#374151}
.ver{background:#dcfce7;color:#166534}.draft{background:#fef3c7;color:#92400e}
.match{border:1px solid #d1d5db;border-radius:8px;padding:10px 12px;margin:10px 0;page-break-inside:avoid}
.muted{color:#6b7280;font-size:12px} .bad{color:#b91c1c;font-weight:700} .ok{color:#166534;font-weight:700}
@media print{body{margin:0}}
"""


def build_report_html(d: Dict[str, Any]) -> str:
    case = d["case"]
    evidence: List[Dict[str, Any]] = d["evidence"]
    matches: List[Dict[str, Any]] = d["matches"]
    findings: List[Dict[str, Any]] = d.get("findings", [])
    auto_dets: List[Dict[str, Any]] = d.get("auto_detections", [])
    chain = d.get("chain") or {}
    generated = d.get("generated_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    ev_name = {e["id"]: e["file_name"] for e in evidence}

    keywords = [m for m in matches if m["kind"] == "KEYWORD"]
    matches = [m for m in matches if m["kind"] != "KEYWORD"]
    strong = [m for m in matches if m["strength"] in ("STRONG", "MEDIUM")]
    weak = [m for m in matches if m["strength"] == "WEAK"]
    verified = [f for f in findings if f.get("verification_status") == "Verified"]
    drafts = [f for f in findings if f.get("verification_status") != "Verified"]

    o: List[str] = []
    o.append(f"<!doctype html><html><head><meta charset='utf-8'><title>Case Report {_E(case.get('case_number',''))}</title>"
             f"<style>{_CSS}</style></head><body>")
    o.append(f"<h1>Investigation Report</h1><div class='muted'>ForenSight AI · generated {_E(generated)}</div>")
    o.append("<div class='banner'><strong>Assistive analysis only.</strong> This report summarises machine-generated "
             "observations and cross-evidence correlations. It does not establish guilt, identity, intent or any legal "
             "conclusion. Items marked <em>unverified</em> have not been reviewed by an investigator. All findings must be "
             "confirmed by a qualified person before being relied upon.</div>")

    # 1. case
    o.append("<h2>1. Case</h2><table>")
    for k, v in (("Case number", case.get("case_number")), ("Title", case.get("title")),
                 ("Status", case.get("status")), ("Opened by", case.get("created_by_name")),
                 ("Opened", case.get("created_at")), ("Description", case.get("description"))):
        o.append(f"<tr><th style='width:160px'>{k}</th><td>{_E(str(v or '—'))}</td></tr>")
    o.append("</table>")

    # 2. summary
    o.append("<h2>2. Summary</h2><ul>")
    o.append(f"<li>{len(evidence)} evidence item(s) analysed.</li>")
    o.append(f"<li><strong>{len(strong)}</strong> cross-evidence match(es) of medium or strong strength"
             f"{f', plus {len(weak)} weak appearance-only similarity(ies)' if weak else ''}.</li>")
    o.append(f"<li>{len(verified)} investigator-verified finding(s); {len(drafts) + len(auto_dets)} unverified machine observation(s).</li>")
    o.append("</ul>")

    # 3. matches
    o.append("<h2>3. Matching clues across evidence</h2>")
    if not matches:
        o.append("<p class='muted'>No clue appears in more than one evidence item.</p>")
    for m in strong + weak:
        cls = m["strength"].lower()
        o.append("<div class='match'>")
        o.append(f"<span class='tag {cls}'>{_E(m['strength'])}</span> "
                 f"<span class='tag {'ver' if m['verified'] else 'draft'}'>{'verified' if m['verified'] else 'unverified'}</span> "
                 f"<strong>{_E(m['kind'])}: {_t(m['value'])}</strong> "
                 f"<span class='muted'>score {_pct(m['score'])} · {_E(m['match_type'])}</span>")
        o.append(f"<p style='margin:6px 0'>{_t(m['explanation'])}</p>")
        o.append("<table><tr><th>Evidence</th><th>When</th><th>Source</th><th>Reading</th><th>Conf.</th><th>Context</th></tr>")
        for mem in m["members"]:
            o.append(f"<tr><td>{_E(mem['file_name'])}</td><td class='mono'>{_E(mem['timestamp_str'] or 'whole file')}</td>"
                     f"<td>{_E(str(mem['source']))}</td><td>{_t(mem['value'])}</td><td>{_pct(mem['confidence'])}</td>"
                     f"<td>{_t(mem.get('context') or '')}</td></tr>")
        o.append("</table></div>")

    if keywords:
        o.append("<h3>Shared keywords</h3><p class='muted'>Words that appear in more than one evidence item. "
                 "Keyword overlap alone is weak: ordinary words can coincide by chance.</p>"
                 "<table><tr><th>Keyword</th><th>Evidence</th><th>Score</th></tr>")
        for m in keywords[:60]:
            files = ", ".join(sorted({mem["file_name"] for mem in m["members"]}))
            o.append(f"<tr><td>{_t(m['value'])}</td><td>{_E(files)}</td><td>{_pct(m['score'])}</td></tr>")
        o.append("</table>")

    # people involved + the investigator's designations
    people = d.get("people") or []
    if people:
        o.append("<h2>People involved</h2>")
        o.append("<p class='muted'>Everyone named, badged or carded in the evidence. A role below is the "
                 "<strong>investigator's own designation</strong> (who, when, and on what basis). ForenSight does not "
                 "determine guilt; a suggestion is only a nearby word in the evidence and is shown as such.</p>")
        o.append("<table><tr><th>Person</th><th>Identifiers</th><th>Role</th><th>Designated by / basis</th>"
                 "<th>Seen in</th></tr>")
        label = {"GUILTY": "Guilty (investigator's determination)", "SUSPECT": "Suspect", "VICTIM": "Victim",
                 "WITNESS": "Witness", "PERSON_OF_INTEREST": "Person of interest", "CLEARED": "Cleared"}
        for p in people:
            ids = ", ".join(i["value"] for i in p.get("identifiers", [])) or "-"
            role = p.get("role")
            if role:
                role_txt = label.get(role, role)
                des = p.get("designation") or {}
                by = (f"{des.get('by') or p.get('role_source') or ''} {des.get('at') or ''}".strip()
                      + (f" - basis: {des['basis']}" if des.get("basis") else ""))
            else:
                role_txt = "not assigned" + (
                    f" (suggested: {p['suggested_role'].title()} - {p.get('suggested_reason')})"
                    if p.get("suggested_role") else "")
                by = "-"
            seen = ", ".join(sorted({s["file_name"] for s in p.get("support", [])})) or "-"
            cls = "bad" if role == "GUILTY" else ""
            o.append(f"<tr><td><strong>{_E(str(p['name']))}</strong></td><td class='mono'>{_E(ids)}</td>"
                     f"<td class='{cls}'>{_E(role_txt)}</td><td>{_E(by)}</td><td>{_E(seen)}</td></tr>")
        o.append("</table>")
        if any(p.get("role") == "GUILTY" for p in people):
            o.append("<div class='banner'>A 'guilty' designation is a determination recorded by the named "
                     "investigator. It is not a finding of this system and is not a legal verdict.</div>")

    # 4. verified findings
    o.append("<h2>4. Investigator-verified findings</h2>")
    if not verified:
        o.append("<p class='muted'>No findings have been verified yet.</p>")
    else:
        o.append("<table><tr><th>Evidence</th><th>Frame time</th><th>Label</th><th>Readout</th><th>Conf.</th>"
                 "<th>Verified by</th><th>Crop SHA-256</th></tr>")
        for f in verified:
            o.append(f"<tr><td>{_E(ev_name.get(f['evidence_id'], f['evidence_id']))}</td>"
                     f"<td class='mono'>{_E(str(f.get('timestamp_str') or ''))}</td><td>{_t(f['label'])}</td>"
                     f"<td>{_t(f.get('readout_text'))}</td><td>{_pct(f['confidence'])}</td>"
                     f"<td>{_E(str(f.get('verified_by') or ''))}</td><td class='mono'>{_E(str(f.get('crop_sha256') or ''))}</td></tr>")
        o.append("</table>")

    # 5. unverified
    o.append("<h2>5. Unverified machine observations</h2>")
    o.append("<p class='muted'>Produced automatically (object detection / OCR / local VLM). Listed for completeness; "
             "not reviewed.</p>")
    rows = [(f, "operator ROI scan") for f in drafts] + [(a, "automatic detector") for a in auto_dets]
    if rows:
        o.append("<table><tr><th>Evidence</th><th>Time</th><th>Observation</th><th>Origin</th><th>Conf.</th></tr>")
        for f, origin in rows[:200]:
            o.append(f"<tr><td>{_E(ev_name.get(f['evidence_id'], f['evidence_id']))}</td>"
                     f"<td class='mono'>{_E(str(f.get('timestamp_str') or ''))}</td><td>{_t(f['label'])}</td>"
                     f"<td>{origin}</td><td>{_pct(f['confidence'])}</td></tr>")
        o.append("</table>")
        if len(rows) > 200:
            o.append(f"<p class='muted'>{len(rows) - 200} further observations omitted for length.</p>")
    else:
        o.append("<p class='muted'>None.</p>")

    # 6. evidence inventory
    o.append("<h2>6. Evidence inventory &amp; integrity</h2>")
    o.append("<table><tr><th>File</th><th>Type</th><th>SHA-256</th><th>Uploaded</th><th>Location</th><th>Auto-analysis</th></tr>")
    for e in evidence:
        loc = (f"{e['latitude']:.5f}, {e['longitude']:.5f}" if e.get("latitude") is not None else "—")
        o.append(f"<tr><td>{_E(e['file_name'])}</td><td>{_E(e['file_type'])}</td>"
                 f"<td class='mono'>{_E(str(e.get('file_hash_sha256') or 'not recorded'))}</td>"
                 f"<td>{_E(str(e.get('uploaded_at') or ''))}</td><td>{_E(loc)}</td>"
                 f"<td>{_E(str(e.get('analysis_status') or 'NOT_RUN'))}</td></tr>")
    o.append("</table>")

    # 7. custody
    o.append("<h2>7. Chain of custody</h2>")
    if chain:
        okcls = "ok" if chain.get("ok") else "bad"
        txt = (f"Hash chain verified intact over {chain.get('entries_checked')} entries."
               if chain.get("ok") else f"CHAIN BROKEN at entry #{chain.get('broken_at_seq')}: {chain.get('reason')}")
        o.append(f"<p class='{okcls}'>{_E(txt)}</p><p class='mono'>head hash: {_E(str(chain.get('head_hash')))}</p>")
    else:
        o.append("<p class='muted'>Chain status unavailable at generation time.</p>")

    # 8. method & limits
    cap = d.get("capabilities") or {}
    o.append("<h2>8. Method &amp; limitations</h2><ul>")
    o.append(f"<li>Object detection: {_E(str(cap.get('detector_model', 'YOLOv8')))} (pre-trained COCO checkpoint, "
             "not fine-tuned on forensic data); coarse colour from HSV statistics.</li>")
    o.append("<li>Text: EasyOCR (pre-trained); OCR errors are expected — near-identical readings are linked as "
             "<em>OCR variant</em> or <em>fuzzy</em> matches and flagged for review.</li>")
    o.append("<li>Appearance-only matches (same object class and colour) are weak and never imply the same object or person.</li>")
    o.append("<li>Locations come from EXIF GPS or manual entry and may be absent or inaccurate.</li>")
    o.append("<li>Local VLM output (operator ROI scans) is schema-constrained and passed through an objective-lexicon filter.</li>")
    o.append("</ul>")
    o.append("</body></html>")
    return "".join(o)
