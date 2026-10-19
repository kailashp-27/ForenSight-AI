"""
backend/modules/case_summary.py
───────────────────────────────
The investigator's "what do we actually have" view, assembled from the clue
pool and the cross-evidence matches:

  people    victim / suspect / witness — name, role, photo(s), who says so
  ids       badge, visitor, employee, account and serial identifiers
  items     tool / weapon / stolen item / device / bag
  vehicles  getaway vehicle (colour + type) and its number plate(s)

Every entry carries SUPPORT: the individual observations from other evidence
that mention it (speech, chat, PDF text, scans, video), and how strongly the
correlation engine ties them together. Investigator-assigned roles and names
(set when a finding is verified) always win over automatic cues, and are
labelled as such.

Honesty rules:
  * a role guessed from a nearby word ("suspect", "victim") is marked
    `role_source = "text cue"` and `needs_review`, never presented as fact;
  * photos are crops of what the investigator or detector actually saw;
  * the module does not decide who is guilty — it lists who is described how.
Pure functions over plain dicts.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz

from backend.modules.clue_terms import COLOURS, ITEMS, VEHICLES, extract_terms, object_key

_RANK = {"STRONG": 3, "MEDIUM": 2, "WEAK": 1, None: 0}

_ROLE_CUES = {
    "VICTIM": ("victim", "complainant", "injured", "deceased", "robbed", "owner of", "mugged"),
    "SUSPECT": ("suspect", "thief", "robber", "accused", "culprit", "perpetrator", "offender", "intruder",
                "criminal", "burglar", "assailant", "suspected"),
    "WITNESS": ("witness", "eyewitness", "bystander"),
}
PERSON_ROLES = {"VICTIM", "SUSPECT", "WITNESS"}
ITEM_ROLES = {"ITEM", "WEAPON", "TOOL", "STOLEN"}

_ITEM_CLASS = {
    "WEAPON": {"knife", "gun"},
    "TOOL": {"crowbar", "hammer", "rope", "stick", "bat"},
    "DEVICE": {"usb drive", "hard drive", "cell phone", "laptop", "camera"},
    "CARRIER": {"backpack", "bag", "handbag", "suitcase", "duffel bag", "box"},
}
_ITEM_KEYS = set(ITEMS.values()) | {"usb drive", "hard drive"}
_VEHICLE_CLASSES = set(VEHICLES.values())


def _item_class(key: str) -> str:
    for cls, keys in _ITEM_CLASS.items():
        if key in keys:
            return cls
    return "OTHER"


def _is_vehicle_key(key: str) -> bool:
    words = key.split()
    return bool(words) and words[-1] in _VEHICLE_CLASSES and all(w in COLOURS for w in words[:-1])


def _ts(ms: Optional[int]) -> Optional[str]:
    if ms is None:
        return None
    ms = int(ms)
    h, r = divmod(ms, 3_600_000)
    m, r = divmod(r, 60_000)
    s, milli = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{milli:03d}"


def _support(c: Dict[str, Any], names: Dict[str, str]) -> Dict[str, Any]:
    return {
        "evidence_id": c["evidence_id"], "file_name": names.get(c["evidence_id"], c["evidence_id"]),
        "source": c.get("source"), "at": _ts(c.get("timestamp_ms")),
        "text": (c.get("context") or c.get("value") or "")[:220], "verified": bool(c.get("verified")),
        "clue_id": c.get("id"),
    }


def _dedupe_support(items: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for s in sorted(items, key=lambda s: (not s["verified"], s["file_name"], s["at"] or "")):
        key = (s["evidence_id"], s["source"], s["at"], s["text"][:40])
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out[:limit]


def _photo(d: Dict[str, Any], names: Dict[str, str], caption: str) -> Dict[str, Any]:
    roi = d.get("source") == "VLM_ROI"
    return {
        "url": f"/api/v1/{'findings' if roi else 'detections'}/{d['id']}/crop",
        "caption": caption, "evidence_id": d["evidence_id"],
        "file_name": names.get(d["evidence_id"], d["evidence_id"]),
        "at": d.get("timestamp_str"), "source": d.get("source"),
        "verified": d.get("verification_status") == "Verified",
        "role": d.get("role"),
    }


def _details(d: Dict[str, Any]) -> List[str]:
    import json
    try:
        return [str(x) for x in json.loads(d.get("details_json") or "[]")]
    except (TypeError, ValueError):
        return []


def _best_strength(clue_ids: set, by_clue: Dict[str, List[Dict[str, Any]]]) -> Optional[str]:
    best = None
    for cid in clue_ids:
        for m in by_clue.get(cid, []):
            if _RANK[m["strength"]] > _RANK[best]:
                best = m["strength"]
    return best


def _name_tokens(name: str) -> set:
    return {t for t in re.findall(r"[a-z]+", name.lower()) if len(t) > 1}


def _role_from_text(contexts: List[str]) -> Optional[str]:
    score: Counter = Counter()
    for ctx in contexts:
        low = ctx.lower()
        for role, cues in _ROLE_CUES.items():
            if any(c in low for c in cues):
                score[role] += 1
    return score.most_common(1)[0][0] if score else None


def build_key_findings(ctx: Dict[str, Any], pool: List[Dict[str, Any]], matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    names = {e["id"]: e["file_name"] for e in ctx["evidence"]}
    dets = [d for d in ctx["detections"] if d.get("verification_status") != "Rejected"]
    roi = [d for d in dets if d.get("source") == "VLM_ROI"]
    auto = [d for d in dets if d.get("source") == "AUTO_YOLO"]

    by_clue: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for m in matches:
        for mem in m["members"]:
            by_clue[mem["clue_id"]].append(m)

    # ── people: the full roster (names, badges, ID cards), investigator designations first ──
    from backend.modules.people_roster import build_roster
    people = build_roster(ctx, pool, matches, ctx.get("designations", []))

    # ── identifiers ──────────────────────────────────────────────────────────
    plate_norms = {c["norm_value"] for c in pool if c["kind"] == "PLATE"}
    id_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in pool:
        if c["kind"] == "ID" and c["norm_value"] not in plate_norms and len(c["norm_value"]) >= 4:
            id_groups[c["norm_value"]].append(c)
    ids = []
    for norm, cl in id_groups.items():
        ids.append({
            "id": f"id:{norm}", "value": max(cl, key=lambda c: c.get("confidence") or 0)["value"],
            "verified": any(c.get("verified") for c in cl),
            "evidence_count": len({c["evidence_id"] for c in cl}),
            "strength": _best_strength({c["id"] for c in cl}, by_clue),
            "support": _dedupe_support([_support(c, names) for c in cl]),
            "label": next((c["context"][:60] for c in cl if c.get("source") == "VLM_ROI"), None),
        })
    ids.sort(key=lambda i: (not i["verified"], -_RANK[i["strength"]], -i["evidence_count"], i["value"]))

    # ── items ────────────────────────────────────────────────────────────────
    item_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in pool:
        if c["kind"] == "OBJECT":
            key = object_key(c["norm_value"] or c["value"])
            if key in _ITEM_KEYS:
                item_groups[key].append(c)
    items = []
    for key, cl in item_groups.items():
        roles = [c.get("role") for c in cl if c.get("role") in ITEM_ROLES]
        photos = []
        for d in roi + auto:
            blob = " ".join([d.get("class_name") or "", d.get("label") or ""] + _details(d))
            if object_key(d.get("class_name") or d.get("label") or "") == key or \
                    any(c.kind == "OBJECT" and object_key(c.norm) == key for c in extract_terms(blob)):
                photos.append(_photo(d, names, f"{d.get('label')} — {d.get('timestamp_str') or ''}".strip(" —")))
        items.append({
            "id": f"item:{key}", "name": key, "display": Counter(c["value"] for c in cl).most_common(1)[0][0],
            "item_class": _item_class(key),
            "role": Counter(roles).most_common(1)[0][0] if roles else None,
            "role_source": "investigator" if roles else None,
            "verified": any(c.get("verified") for c in cl),
            "evidence_count": len({c["evidence_id"] for c in cl}),
            "strength": _best_strength({c["id"] for c in cl}, by_clue),
            "photos": photos[:4], "support": _dedupe_support([_support(c, names) for c in cl]),
        })
    items.sort(key=lambda i: (not i["verified"], -_RANK[i["strength"]], -i["evidence_count"], i["name"]))

    # ── vehicles + plates ────────────────────────────────────────────────────
    veh_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in pool:
        if c["kind"] == "OBJECT":
            key = object_key(c["norm_value"] or c["value"])
            if _is_vehicle_key(key):
                veh_groups[key].append(c)

    plate_entries: List[Dict[str, Any]] = []
    in_match: set = set()
    for m in matches:
        if m["kind"] != "PLATE":
            continue
        cids = {mem["clue_id"] for mem in m["members"]}
        in_match |= cids
        plate_entries.append({
            "plate": m["value"], "strength": m["strength"], "match_type": m["match_type"],
            "verified": m["verified"], "evidence_count": len(m["evidence_ids"]),
            "support": _dedupe_support([{
                "evidence_id": mem["evidence_id"], "file_name": mem["file_name"], "source": mem["source"],
                "at": mem["timestamp_str"], "text": mem.get("context") or mem["value"],
                "verified": mem.get("verified", False), "clue_id": mem["clue_id"]} for mem in m["members"]]),
            "_ev": set(m["evidence_ids"]), "_ts": [mem["timestamp_ms"] for mem in m["members"] if mem["timestamp_ms"] is not None],
        })
    for c in pool:
        if c["kind"] == "PLATE" and c["id"] not in in_match:
            plate_entries.append({
                "plate": c["value"], "strength": None, "match_type": None, "verified": bool(c.get("verified")),
                "evidence_count": 1, "support": [_support(c, names)],
                "_ev": {c["evidence_id"]}, "_ts": [c["timestamp_ms"]] if c.get("timestamp_ms") is not None else [],
            })

    vehicles = []
    for key, cl in veh_groups.items():
        ev = {c["evidence_id"] for c in cl}
        ts = [c["timestamp_ms"] for c in cl if c.get("timestamp_ms") is not None]
        linked = []
        for p in plate_entries:
            same_ev = p["_ev"] & ev
            close = any(abs(a - b) <= 20_000 for a in p["_ts"] for b in ts)
            if same_ev and (close or len(veh_groups) == 1):
                linked.append(p)
        if not linked and len(veh_groups) == 1:
            linked = list(plate_entries)          # the only vehicle in the case: attribute (flagged below)
        photos = [_photo(d, names, f"{d.get('label')} — {d.get('timestamp_str') or ''}".strip(" —"))
                  for d in roi + auto
                  if object_key(d.get("class_name") or d.get("label") or "") == key
                  or (d.get("category") == "VEHICLE" and _is_vehicle_key(object_key(d.get("label") or "")))][:4]
        vehicles.append({
            "id": f"veh:{key}", "description": key, "display": Counter(c["value"] for c in cl).most_common(1)[0][0],
            "verified": any(c.get("verified") for c in cl),
            "evidence_count": len(ev), "strength": _best_strength({c["id"] for c in cl}, by_clue),
            "plates": [{k: v for k, v in p.items() if not k.startswith("_")} for p in linked],
            "plate_inferred": bool(linked) and len(veh_groups) == 1,
            "photos": photos, "support": _dedupe_support([_support(c, names) for c in cl]),
        })
    linked_plates = {p["plate"] for v in vehicles for p in v["plates"]}
    loose = [{k: v for k, v in p.items() if not k.startswith("_")} for p in plate_entries if p["plate"] not in linked_plates]
    vehicles.sort(key=lambda v: (not v["verified"], -_RANK[v["strength"]], -v["evidence_count"]))
    loose.sort(key=lambda p: (not p["verified"], -_RANK[p["strength"]], -p["evidence_count"]))

    return {
        "people": people, "ids": ids[:40], "items": items, "vehicles": vehicles, "unlinked_plates": loose,
        "totals": {"people": len(people), "ids": len(ids), "items": len(items),
                   "vehicles": len(vehicles), "plates": len(plate_entries),
                   "investigator_roles": sum(1 for p in people if p.get("role_source"))},
        "notes": ["Roles marked 'text cue' were inferred from a nearby word in the evidence and need review.",
                  "Roles and names set by an investigator when verifying a finding always take priority."],
    }
