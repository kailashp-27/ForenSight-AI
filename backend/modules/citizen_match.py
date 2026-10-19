"""
backend/modules/citizen_match.py
────────────────────────────────
Suggests which citizen-register entry a person found in a case MIGHT be.

This is a SUGGESTION engine, never an identification:
  * a name is weak evidence — people share names (the register itself has two
    "Arthur Dent"s and three Dents), so name-only matches are capped at LIKELY
    and are labelled with how many citizens share the name;
  * a phone number found in the same scan/message as the person is stronger;
  * nothing is linked for real until an investigator confirms it, and a
    rejected pairing is never suggested again.

Scoring (additive, capped at 0.99):
    full name equal ...................... 0.75
    name contained (middle name etc.) .... 0.65
    first-name variant + same surname .... 0.62   ("Jon Vance" / "Jonathan Vance")
    initial + same surname ............... 0.58   ("J. Vance"  / "Jonathan Vance")
    surname only ......................... 0.30
    phone number equal ................... +0.60
Levels:  >= 0.85 STRONG · >= 0.55 LIKELY · >= 0.40 POSSIBLE · below: not shown
Pure functions.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

from rapidfuzz import fuzz

SHOW_THRESHOLD = 0.40
ALERT_THRESHOLD = 0.55                 # a suggested link counts toward a cross-case alert from here up


def tokens(name: str) -> List[str]:
    return [t for t in re.sub(r"[^a-z ]+", " ", (name or "").lower().replace("-", " ")).split() if t]


def level_for(score: float) -> Optional[str]:
    if score >= 0.85:
        return "STRONG"
    if score >= ALERT_THRESHOLD:
        return "LIKELY"
    if score >= SHOW_THRESHOLD:
        return "POSSIBLE"
    return None


def _phone_equal(a: str, b: str) -> bool:
    a, b = re.sub(r"\D", "", a or ""), re.sub(r"\D", "", b or "")
    n = min(len(a), len(b))
    return n >= 7 and (a.endswith(b) or b.endswith(a))


def _name_score(v: List[str], c: List[str]) -> tuple:
    """(score, reason) for one name variant against one citizen name."""
    if not v or not c:
        return 0.0, ""
    last_c = c[-1]
    if set(v) == set(c) and len(v) >= 2:
        return 0.75, "full name is identical"
    if len(v) >= 2 and set(v) <= set(c) and v[-1] == last_c:
        return 0.65, "name is contained in the register name"
    if len(v) >= 2 and v[-1] == last_c:
        f, cf = v[0], c[0]
        if len(f) == 1 and cf.startswith(f):
            return 0.58, f"initial “{f.upper()}.” and surname match “{c[0].title()} {last_c.title()}”"
        if len(f) >= 2 and (cf.startswith(f) or f.startswith(cf) or fuzz.ratio(f, cf) >= 80):
            return 0.62, f"first name “{f}” is a variant of “{cf}” and the surname matches"
    if len(v) == 1 and v[0] == last_c and len(v[0]) >= 3:
        return 0.30, f"surname “{last_c.title()}” matches"
    return 0.0, ""


def candidates_for(
    person: Dict[str, Any],
    citizens: List[Dict[str, Any]],
    index: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    rejected: Iterable[int] = (),
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """
    person: roster entry (name, aliases, identifiers[{kind, value}]).
    citizens: register rows (id, full_name, norm_name, phone ...).
    Returns the best candidates with score, level and the reasons.
    """
    rejected = set(rejected)
    variants = [tokens(person["name"])] + [tokens(a) for a in person.get("aliases", [])]
    variants = [v for v in variants if v and not any(len(t) <= 1 for t in v[1:])]   # skip handles like "jv ops"
    phones = [i["value"] for i in person.get("identifiers", []) if i.get("kind") == "PHONE"]

    if index is None:
        index = defaultdict(list)
        for c in citizens:
            ct = tokens(c["full_name"])
            if ct:
                index[ct[-1]].append(c)
    pool: Dict[int, Dict[str, Any]] = {}
    for v in variants:
        for c in index.get(v[-1], []):
            pool[c["id"]] = c
    for c in citizens:
        if phones and c.get("phone") and any(_phone_equal(p, c["phone"]) for p in phones):
            pool[c["id"]] = c

    scored = []
    for c in pool.values():
        if c["id"] in rejected:
            continue
        ct = tokens(c["full_name"])
        best, reason = 0.0, ""
        for v in variants:
            s, why = _name_score(v, ct)
            if s > best:
                best, reason = s, why
        reasons = [reason] if reason else []
        score = best
        if phones and c.get("phone") and any(_phone_equal(p, c["phone"]) for p in phones):
            score += 0.60
            reasons.append(f"phone number {c['phone']} appears next to this person")
        scored.append({"citizen": c, "score": min(0.99, score), "reasons": reasons})

    # Name-only matches are ambiguous when several citizens fit equally well.
    top = max((s["score"] for s in scored), default=0.0)
    ties = [s for s in scored if abs(s["score"] - top) < 1e-9]
    out = []
    for s in sorted(scored, key=lambda x: (-x["score"], x["citizen"]["id"])):
        score, reasons = s["score"], list(s["reasons"])
        phone_hit = any("phone number" in r for r in reasons)
        if not phone_hit and len(ties) > 1 and s in ties:
            reasons.append(f"{len(ties)} citizens fit this name equally — pick the right one or reject")
            score = min(score, 0.54)            # ambiguous name-only: never above POSSIBLE
        lvl = level_for(score)
        if lvl:
            c = s["citizen"]
            out.append({"citizen_id": c["id"], "full_name": c["full_name"], "score": round(score, 2),
                        "level": lvl, "reasons": reasons})
    return out[:limit]
