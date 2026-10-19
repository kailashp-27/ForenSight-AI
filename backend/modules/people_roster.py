"""
backend/modules/people_roster.py
────────────────────────────────
The roster of EVERY person involved in a case, assembled from what the
evidence itself contains, so an investigator can decide who is who.

A person can surface through:
  * a name in speech, a PDF, a chat message or a scan note,
  * the author of chat messages,
  * a badge / ID card / visitor pass read from a scan or document
    (kept as an identifier on the person, or as an "unidentified holder"
    entry when no name sits next to it),
  * a person the investigator added by hand.

Names that obviously refer to the same person are merged ("J. Vance",
"j.vance", "Mr Vance"); the investigator can also merge entries or attach an
ID to a person, and those choices are remembered as aliases.

Roles:  the investigator's designation always wins. The system only ever
SUGGESTS victim / suspect / witness, from a nearby word, and labels it as a
suggestion. It never suggests, and never sets, "guilty": that value exists only
as an explicit, attributed, audited determination made by a person
(see routes/investigation.py), and is rendered as such everywhere.

Pure functions over plain dicts.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz

ROLES = ["UNASSIGNED", "VICTIM", "SUSPECT", "PERSON_OF_INTEREST", "WITNESS", "CLEARED", "GUILTY"]
SUGGESTABLE = {"VICTIM", "SUSPECT", "WITNESS"}          # the system may only ever suggest these
_ORDER = {r: i for i, r in enumerate(["GUILTY", "SUSPECT", "VICTIM", "PERSON_OF_INTEREST", "WITNESS", "CLEARED"])}

_CUES = {
    "VICTIM": ("victim", "complainant", "injured", "deceased", "robbed", "mugged"),
    "SUSPECT": ("suspect", "thief", "robber", "accused", "culprit", "perpetrator", "offender", "intruder",
                "burglar", "assailant"),
    "WITNESS": ("witness", "eyewitness", "bystander"),
}
_BADGE_CONTEXT = re.compile(r"badge|visitor|pass\b|employee|staff|\bid\b|id card|identity|lanyard|card", re.I)
_FROM_INVESTIGATOR_ROLE = {"VICTIM", "SUSPECT", "WITNESS"}


_BEFORE, _AFTER = 28, 14          # characters either side of the name that count as "next to it"


def _nearest_cue(context: str, value: str):
    """
    Role word right before the name ("the suspect Mr Iqbal") or just after it
    ("Iqbal, the suspect"). A cue belonging to a neighbouring name must not count.
    Returns (role, word) or None.
    """
    low, name = context.lower(), (value or "").lower()
    idx = low.find(name) if name else -1
    if idx < 0:
        return None
    before, after = low[max(0, idx - _BEFORE):idx], low[idx + len(name): idx + len(name) + _AFTER]
    best = None
    for role, cues in _CUES.items():
        for w in cues:
            p = before.rfind(w)
            if p >= 0:
                dist = len(before) - (p + len(w))
                if best is None or dist < best[0]:
                    best = (dist, role, w)
            q = after.find(w)
            if q >= 0 and (best is None or q + 6 < best[0]):      # after-name cues are weaker
                best = (q + 6, role, w)
    return (best[1], best[2]) if best else None


def norm_name(s: str) -> str:
    return re.sub(r"[\s._\-]+", " ", s or "").lower().strip()


def norm_id(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _tokens(name: str) -> set:
    return {t for t in re.findall(r"[a-z]+", name.lower()) if len(t) > 1}


def _json_list(v: Any) -> List[str]:
    if isinstance(v, list):
        return [str(x) for x in v]
    try:
        out = json.loads(v or "[]")
        return [str(x) for x in out] if isinstance(out, list) else []
    except (TypeError, ValueError):
        return []


def _ts(ms: Optional[int]) -> Optional[str]:
    if ms is None:
        return None
    ms = int(ms)
    h, r = divmod(ms, 3_600_000)
    m, r = divmod(r, 60_000)
    s, milli = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{milli:03d}"


_SOURCE_LABEL = {
    "CHAT": "chat author / message", "VLM_ROI": "scan / badge", "DOCUMENT": "document text",
    "TRANSCRIPT": "speech transcript", "AUTO_OCR": "on-screen text", "AUTO_YOLO": "detector",
    "INVESTIGATOR": "added by investigator",
}


def build_roster(
    ctx: Dict[str, Any],
    pool: List[Dict[str, Any]],
    matches: List[Dict[str, Any]],
    designations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    names = {e["id"]: e["file_name"] for e in ctx["evidence"]}
    dets = {d["id"]: d for d in ctx["detections"] if d.get("verification_status") != "Rejected"}

    by_clue: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for m in matches:
        for mem in m["members"]:
            by_clue[mem["clue_id"]].append(m)

    # ── 1. members: every NAME clue + a virtual member per investigator-known alias ──
    members: List[Dict[str, Any]] = []
    for c in pool:
        if c["kind"] == "NAME":
            members.append({"norm": norm_name(c["norm_value"] or c["value"]), "clue": c, "design": None})
    for d in designations:
        for n in {norm_name(d["display_name"])} | {norm_name(a) for a in _json_list(d.get("aliases")) if not re.fullmatch(r"[A-Z0-9\-]+", a)}:
            if n:
                members.append({"norm": n, "clue": None, "design": d})

    # ── 2. union similar names ──────────────────────────────────────────────
    parent = list(range(len(members)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    order = sorted(range(len(members)), key=lambda i: -len(members[i]["norm"]))
    for a_pos, a in enumerate(order):
        ta = _tokens(members[a]["norm"])
        for b in order[a_pos + 1:]:
            if find(a) == find(b):
                continue
            tb = _tokens(members[b]["norm"])
            same = members[a]["norm"] == members[b]["norm"]
            sub = bool(ta and tb and (tb <= ta or ta <= tb)) and min(len(ta), len(tb)) >= 1 \
                and max(len(x) for x in (ta | tb)) >= 4
            close = fuzz.token_set_ratio(members[a]["norm"], members[b]["norm"]) >= 95 and len(members[a]["norm"]) >= 5
            if same or sub or close:
                parent[find(b)] = find(a)

    groups: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for i, m in enumerate(members):
        groups[find(i)].append(m)

    # ── 3. identifiers (badges / ID cards) tied to a person by sharing a scan or message ──
    plate_norms = {c["norm_value"] for c in pool if c["kind"] == "PLATE"}
    id_clues = [c for c in pool if ((c["kind"] == "ID" and c["norm_value"] not in plate_norms)
                                    or c["kind"] == "PHONE") and len(c["norm_value"]) >= 3]
    record_of = lambda c: c.get("det_id") or c.get("chunk_id")          # noqa: E731  (same scan / same message)
    NEAR = 90        # characters: an ID this close to a name in a document passage belongs with it

    def badge_like(c: Dict[str, Any]) -> bool:
        d = dets.get(c.get("det_id") or "")
        if d and d.get("category") == "TEXT_OR_CODE":
            return True
        return bool(_BADGE_CONTEXT.search(c.get("context") or ""))

    roster: List[Dict[str, Any]] = []
    id_used: set = set()

    for g in groups.values():
        clues = [m["clue"] for m in g if m["clue"] is not None]
        designs = [m["design"] for m in g if m["design"] is not None]
        design = designs[0] if designs else None
        norms = sorted({m["norm"] for m in g}, key=len, reverse=True)
        display = (design["display_name"] if design else None) or \
            (sorted({c["value"] for c in clues}, key=lambda v: (-len(v.split()), -len(v)))[0] if clues else norms[0].title())
        key = design["person_key"] if design else "p:" + re.sub(r"\s+", "-", norms[0])

        rec_ids = {record_of(c) for c in clues if record_of(c)}
        positions: Dict[str, List[int]] = defaultdict(list)
        for c in clues:
            if c.get("chunk_id") and c.get("pos") is not None:
                positions[c["chunk_id"]].append(int(c["pos"]))

        def near_a_name(idc: Dict[str, Any]) -> bool:
            """Same scan/message always counts; within a longer passage the ID must sit next to the name."""
            if idc.get("det_id"):
                return True
            ps = positions.get(idc.get("chunk_id") or "", [])
            if not ps or idc.get("pos") is None:
                return True                      # short message / no offsets: the whole message is the record
            return any(abs(int(idc["pos"]) - p) <= NEAR for p in ps)
        alias_ids = {norm_id(a) for d in designs for a in _json_list(d.get("aliases")) if norm_id(a)}
        idents = []
        for c in id_clues:
            spk = norm_name(c.get("speaker") or "")
            ident_ok = badge_like(c) or c["kind"] == "PHONE"
            same_record = record_of(c) in rec_ids and ident_ok and near_a_name(c)
            if same_record or (c["norm_value"] in alias_ids) or (spk and spk in norms and ident_ok):
                how = ("attached by investigator" if c["norm_value"] in alias_ids and record_of(c) not in rec_ids
                       else "same scan" if c.get("det_id") else "same message / passage"
                       if record_of(c) in rec_ids else "sent by this person")
                idents.append({"value": c["value"], "norm": c["norm_value"], "kind": c["kind"], "how": how,
                               "file_name": names.get(c["evidence_id"], c["evidence_id"]),
                               "at": _ts(c.get("timestamp_ms")), "source": c.get("source")})
                id_used.add(c["id"])
        seen_i = set()
        idents = [i for i in idents if not (i["norm"] in seen_i or seen_i.add(i["norm"]))]

        # photos: the investigator-marked region the person/badge came from
        photos = []
        det_ids = {c.get("det_id") for c in clues if c.get("det_id")} | \
                  {c.get("det_id") for c in id_clues if c["id"] in id_used and c.get("det_id")}
        for did in det_ids:
            d = dets.get(did)
            if d and d.get("source") == "VLM_ROI":
                photos.append({"url": f"/api/v1/findings/{d['id']}/crop",
                               "caption": d.get("label") or "scan", "evidence_id": d["evidence_id"],
                               "file_name": names.get(d["evidence_id"], d["evidence_id"]),
                               "at": d.get("timestamp_str"), "source": "VLM_ROI",
                               "verified": d.get("verification_status") == "Verified", "role": d.get("role")})
        for d in dets.values():
            if d["id"] in det_ids or d.get("source") != "VLM_ROI":
                continue
            subj = norm_name(d.get("subject_name") or "")
            if subj and (_tokens(subj) & set().union(*[_tokens(n) for n in norms]) or subj in norms):
                photos.append({"url": f"/api/v1/findings/{d['id']}/crop", "caption": d.get("label") or "scan",
                               "evidence_id": d["evidence_id"], "file_name": names.get(d["evidence_id"], d["evidence_id"]),
                               "at": d.get("timestamp_str"), "source": "VLM_ROI",
                               "verified": d.get("verification_status") == "Verified", "role": d.get("role")})

        # role: investigator designation > role set on a verified finding > (suggestion only)
        finding_roles = [c.get("role") for c in clues if c.get("role") in _FROM_INVESTIGATOR_ROLE]
        role, role_source = None, None
        if design and design.get("role") and design["role"] != "UNASSIGNED":
            role, role_source = design["role"], "investigator designation"
        elif finding_roles:
            role, role_source = Counter(finding_roles).most_common(1)[0][0], "investigator (verified finding)"
        sug, sug_reason = None, None
        if role is None:
            score: Counter = Counter()
            reason: Dict[str, str] = {}
            for c in clues:
                hit = _nearest_cue(c.get("context") or "", c["value"])
                if hit:
                    r, word = hit
                    score[r] += 1
                    reason.setdefault(r, f"\u201c{word}\u201d next to the name in {names.get(c['evidence_id'], 'evidence')}")
            if score:
                sug = score.most_common(1)[0][0]
                sug_reason = reason[sug]

        supports = [{
            "evidence_id": c["evidence_id"], "file_name": names.get(c["evidence_id"], c["evidence_id"]),
            "source": c.get("source"), "at": _ts(c.get("timestamp_ms")),
            "text": (c.get("context") or c["value"])[:200], "verified": bool(c.get("verified")), "clue_id": c.get("id"),
        } for c in clues]
        seen_s, dedup = set(), []
        for s in sorted(supports, key=lambda s: (not s["verified"], s["file_name"], s["at"] or "")):
            k = (s["evidence_id"], s["source"], s["at"], s["text"][:40])
            if k not in seen_s:
                seen_s.add(k)
                dedup.append(s)

        strength = None
        rank = {"STRONG": 3, "MEDIUM": 2, "WEAK": 1}
        for c in clues:
            for m in by_clue.get(c["id"], []):
                if rank.get(m["strength"], 0) > rank.get(strength, 0):
                    strength = m["strength"]

        roster.append({
            "id": key, "key": key, "name": display,
            "aliases": [v for v in sorted({c["value"] for c in clues}, key=len, reverse=True) if v != display][:6],
            "alias_norms": norms,
            "role": role, "role_source": role_source,
            "suggested_role": sug if sug in SUGGESTABLE else None, "suggested_reason": sug_reason,
            "needs_review": role is None,
            "verified": any(c.get("verified") for c in clues),
            "identifiers": idents, "photos": photos[:4], "support": dedup[:10],
            "evidence_count": len({c["evidence_id"] for c in clues}),
            "found_via": sorted({_SOURCE_LABEL.get(c.get("source") or "", str(c.get("source"))) for c in clues}),
            "strength": strength,
            "manual": bool(design and design.get("is_manual")),
            "designation": ({"basis": design.get("basis"), "by": design.get("designated_by"),
                             "at": design.get("designated_at")} if design and design.get("role") not in (None, "UNASSIGNED") else None),
            "has_designation_row": design is not None,
        })

    # ── 4. badges / ID cards with no name beside them: "unidentified holder" entries ──
    for c in id_clues:
        if c["id"] in id_used or c["kind"] != "ID" or not badge_like(c):
            continue
        norm = c["norm_value"]
        if any(norm == r_i["norm"] for r in roster for r_i in r["identifiers"]):
            continue
        d = dets.get(c.get("det_id") or "")
        key = "id:" + norm
        desig = next((x for x in designations if x["person_key"] == key), None)
        role = desig["role"] if desig and desig.get("role") not in (None, "UNASSIGNED") else None
        roster.append({
            "id": key, "key": key, "name": (desig["display_name"] if desig else f"Holder of {c['value']}"),
            "aliases": [], "alias_norms": [], "role": role,
            "role_source": "investigator designation" if role else None,
            "suggested_role": None, "suggested_reason": None, "needs_review": role is None, "verified": bool(c.get("verified")),
            "identifiers": [{"value": c["value"], "norm": norm, "how": "badge / ID with no name beside it",
                             "file_name": names.get(c["evidence_id"], c["evidence_id"]), "at": _ts(c.get("timestamp_ms")),
                             "source": c.get("source")}],
            "photos": ([{"url": f"/api/v1/findings/{d['id']}/crop", "caption": d.get("label") or "badge",
                         "evidence_id": d["evidence_id"], "file_name": names.get(d["evidence_id"], d["evidence_id"]),
                         "at": d.get("timestamp_str"), "source": "VLM_ROI",
                         "verified": d.get("verification_status") == "Verified", "role": d.get("role")}]
                       if d and d.get("source") == "VLM_ROI" else []),
            "support": [{"evidence_id": c["evidence_id"], "file_name": names.get(c["evidence_id"], c["evidence_id"]),
                         "source": c.get("source"), "at": _ts(c.get("timestamp_ms")),
                         "text": (c.get("context") or c["value"])[:200], "verified": bool(c.get("verified")),
                         "clue_id": c.get("id")}],
            "evidence_count": 1, "found_via": [_SOURCE_LABEL.get(c.get("source") or "", "evidence")],
            "strength": None, "manual": False, "unidentified": True,
            "designation": ({"basis": desig.get("basis"), "by": desig.get("designated_by"),
                             "at": desig.get("designated_at")} if role else None),
            "has_designation_row": desig is not None,
        })

    roster.sort(key=lambda p: (p["role"] is None, _ORDER.get(p["role"] or "", 9), p["suggested_role"] is None,
                               -p["evidence_count"], p["name"].lower()))
    return roster
