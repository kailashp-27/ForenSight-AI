"""
backend/modules/correlation_engine.py
─────────────────────────────────────
Automatic cross-evidence clue correlation.

Given every clue extracted from every evidence item in a case, find the ones
that refer to the same thing in DIFFERENT evidence, and explain why.

Match types (strongest first):
  EXACT        same normalised value (e.g. identical plate / phone / e-mail)
  OCR_VARIANT  equal after folding OCR confusions (O/0, B/8 …)
  FUZZY        string similarity >= FUZZY_THRESHOLD (plates / IDs only)
  APPEARANCE   same object class + colour (weak: "a red car appears in both").

Safeguards (the system is assistive, not judicial):
  • APPEARANCE matches are always labelled WEAK and never imply identity.
  • Every match lists its members with evidence, timestamp and source, so an
    investigator can inspect each underlying observation.
  • Machine matches are flagged `needs_review`; a match is only 'verified'
    when at least one member came from a human-verified finding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from backend.modules.clue_terms import object_key
from backend.modules.clue_text import match_key

FUZZY_THRESHOLD = 88
_TEXT_KINDS = {"PLATE", "PHONE", "EMAIL", "ID", "AMOUNT", "NAME", "TEXT", "DATE", "NUMBER", "KEYWORD",
                "TIME", "LOCATION"}
_FUZZY_KINDS = {"PLATE", "ID", "NAME", "ALNUM"}
# A plate read by OCR, a partly read plate from a regional scan, a plate typed in a PDF and a
# camera/serial identifier are all "alphanumeric identifiers": compared together, not by label.
_ALNUM_FAMILY = {"PLATE", "ID", "TEXT"}
# Names and free text are weaker evidence of identity than a plate or a phone number:
# they can never reach STRONG on their own.
# A shared everyday word is weak evidence: keyword overlap is reported (so nothing said or
# written is lost) but capped well below MEDIUM.
_KIND_WEIGHT = {"NAME": 0.8, "TEXT": 0.8, "DATE": 0.75, "NUMBER": 0.8, "KEYWORD": 0.5,
                "TIME": 0.6, "LOCATION": 0.8}

_BASE_SCORE = {"EXACT": 0.95, "OCR_VARIANT": 0.85, "PARTIAL": 0.65, "FUZZY": 0.70, "APPEARANCE": 0.35}
_STRENGTH = [(0.8, "STRONG"), (0.6, "MEDIUM"), (0.0, "WEAK")]


@dataclass
class _Cluster:
    kind: str
    members: List[Dict[str, Any]] = field(default_factory=list)
    keys: set = field(default_factory=set)
    exact_norms: set = field(default_factory=set)
    fuzzy: bool = False
    partial: bool = False


def _strength(score: float) -> str:
    for threshold, name in _STRENGTH:
        if score >= threshold:
            return name
    return "WEAK"


def _ts_str(ms: Optional[int]) -> Optional[str]:
    if ms is None:
        return None
    ms = int(ms)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}:{milli:03d}"


def correlate(clues: List[Dict[str, Any]], evidence: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    clues:    dicts with id, evidence_id, kind, value, norm_value, confidence,
              source, timestamp_ms, context, verified (bool), bbox
    evidence: {evidence_id: {file_name, file_type}}
    Returns match dicts sorted strongest-first.
    """
    matches: List[Dict[str, Any]] = []

    # ── text-like clues: union by key, then fuzzy-merge ─────────────────────
    clusters: List[_Cluster] = []
    by_key: Dict[tuple, _Cluster] = {}
    for c in clues:
        if c["kind"] not in _TEXT_KINDS or not c.get("norm_value"):
            continue
        ckind = "ALNUM" if c["kind"] in _ALNUM_FAMILY else c["kind"]
        key = (ckind, match_key("ID" if ckind == "ALNUM" else ckind, c["norm_value"]))
        cl = by_key.get(key)
        if cl is None:
            cl = _Cluster(kind=ckind, keys={key})
            by_key[key] = cl
            clusters.append(cl)
        cl.members.append(c)
        cl.exact_norms.add(c["norm_value"])

    # Fuzzy merge between clusters of the same kind (small n → O(n²) is fine)
    merged = True
    while merged:
        merged = False
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                a, b = clusters[i], clusters[j]
                if a.kind != b.kind or a.kind not in _FUZZY_KINDS:
                    continue
                ka = next(iter(a.keys))[1]
                kb = next(iter(b.keys))[1]
                if a.kind == "NAME":
                    # "Ramesh" and "Ramesh Kumar" are one person mentioned two ways.
                    if min(len(ka), len(kb)) < 4:
                        continue
                    similar = fuzz.token_set_ratio(ka, kb) >= 95 or fuzz.ratio(ka, kb) >= FUZZY_THRESHOLD
                elif a.kind == "ALNUM":
                    short, long_ = (ka, kb) if len(ka) <= len(kb) else (kb, ka)
                    if len(short) < 5:
                        continue
                    # a real identifier (letters AND digits) inside a longer reading, e.g.
                    # "RACK04" inside "SERVERRACK04", or "TX882" inside "TX882V"
                    ident_like = bool(re.search(r"[A-Z]", short) and re.search(r"\d", short))
                    contained = (short in long_ and len(short) >= 5
                                 and len(short) >= int(len(long_) * (0.45 if ident_like else 0.7)))
                    allowed = 1 if len(long_) <= 8 else 2          # edit distance budget
                    close = Levenshtein.distance(ka, kb) <= allowed and abs(len(ka) - len(kb)) <= allowed
                    similar = contained or close
                    if similar and contained and not close:
                        a.partial = True
                else:
                    if min(len(ka), len(kb)) < 6:
                        continue
                    similar = fuzz.ratio(ka, kb) >= FUZZY_THRESHOLD
                if similar:
                    a.members.extend(b.members)
                    a.keys |= b.keys
                    a.exact_norms |= b.exact_norms
                    a.partial = a.partial or b.partial
                    a.fuzzy = True
                    del clusters[j]
                    merged = True
                    break
            if merged:
                break

    for cl in clusters:
        ev_ids = {m["evidence_id"] for m in cl.members}
        if len(ev_ids) < 2:
            continue
        if cl.partial:
            mtype = "PARTIAL"
        elif cl.fuzzy:
            mtype = "FUZZY"
        elif len(cl.exact_norms) > 1:
            mtype = "OCR_VARIANT"
        else:
            mtype = "EXACT"
        kinds = {m["kind"] for m in cl.members}
        out_kind = ("PLATE" if "PLATE" in kinds else "ID" if "ID" in kinds else "TEXT") \
            if cl.kind == "ALNUM" else cl.kind
        matches.append(_build_match(out_kind, mtype, cl.members, evidence,
                                    sorted(cl.exact_norms)))

    # ── appearance (object class + colour) — weak by design ─────────────────
    app: Dict[tuple, List[Dict[str, Any]]] = {}
    for c in clues:
        if c["kind"] != "OBJECT":
            continue
        app.setdefault(object_key(c.get("norm_value") or c["value"]), []).append(c)
    for key, members in app.items():
        if len({m["evidence_id"] for m in members}) >= 2:
            matches.append(_build_match("OBJECT", "APPEARANCE", members, evidence, [key]))

    matches.sort(key=lambda m: (-m["score"], m["kind"], m["id"]))
    return matches


def _build_match(kind: str, mtype: str, members: List[Dict[str, Any]],
                 evidence: Dict[str, Dict[str, Any]], norms: List[str]) -> Dict[str, Any]:
    ev_ids = sorted({m["evidence_id"] for m in members})
    verified = any(m.get("verified") for m in members)
    avg_conf = sum(float(m.get("confidence") or 0) for m in members) / max(1, len(members))
    score = _BASE_SCORE[mtype]
    # Low-confidence OCR reads should not produce STRONG matches.
    score = score * _KIND_WEIGHT.get(kind, 1.0)
    if kind == "KEYWORD":   # rarer words are more distinctive
        score *= max(0.3, sum(float(m.get("weight", 0.5)) for m in members) / max(1, len(members)))
    score = round(min(0.99, score * (0.75 + 0.25 * avg_conf) + (0.05 if verified else 0)), 3)

    display = max(members, key=lambda m: float(m.get("confidence") or 0))["value"]
    if mtype == "APPEARANCE":
        why = (f"An object described as '{display}' was detected in {len(ev_ids)} different "
               "evidence items. This is an appearance-only similarity and does not establish "
               "that it is the same object.")
    elif mtype == "EXACT" and kind == "KEYWORD":
        why = (f"The word '{display}' appears in {len(ev_ids)} different evidence items. This is keyword "
               "overlap only; ordinary words can coincide by chance, so check the passages.")
    elif mtype == "EXACT":
        why = f"The identical {kind.lower()} '{display}' appears in {len(ev_ids)} different evidence items."
    elif mtype == "PARTIAL":
        why = (f"The readings {', '.join(repr(n) for n in norms)} overlap: the shorter one is contained in "
               f"the longer, which is typical of a partly read {kind.lower()}. Review the sources to confirm.")
    elif mtype == "OCR_VARIANT":
        why = (f"{kind.title()} readings {', '.join(repr(n) for n in norms)} differ only by common "
               f"OCR character confusions and are treated as the same {kind.lower()}.")
    else:
        why = (f"{kind.title()} readings {', '.join(repr(n) for n in norms)} are highly similar "
               f"(>= {FUZZY_THRESHOLD}% string similarity); review the sources to confirm.")

    out_members = []
    for m in sorted(members, key=lambda x: (x["evidence_id"], x.get("timestamp_ms") or 0)):
        info = evidence.get(m["evidence_id"], {})
        out_members.append({
            "clue_id": m["id"],
            "evidence_id": m["evidence_id"],
            "file_name": info.get("file_name", m["evidence_id"]),
            "file_type": info.get("file_type"),
            "value": m["value"],
            "source": m.get("source"),
            "timestamp_ms": m.get("timestamp_ms"),
            "timestamp_str": _ts_str(m.get("timestamp_ms")),
            "confidence": float(m.get("confidence") or 0),
            "context": m.get("context"),
            "norm_value": m.get("norm_value"),
            "bbox": m.get("bbox"),
            "verified": bool(m.get("verified")),
        })

    return {
        "id": f"{kind}:{mtype}:{'|'.join(norms)}"[:180],
        "kind": kind,
        "match_type": mtype,
        "value": display,
        "score": score,
        "strength": _strength(score) if mtype != "APPEARANCE" else "WEAK",
        "evidence_ids": ev_ids,
        "occurrences": len(members),
        "explanation": why,
        "verified": verified,
        "needs_review": not verified,
        "members": out_members,
    }
