"""
backend/modules/graph_engine.py
───────────────────────────────
Entity relationship graph (Person / Vehicle / Item / Text / Evidence) built
from VERIFIED findings only — unverified AI drafts never reach the graph.

Neo4j is not part of this deployment, so the graph is derived on demand from
the relational tables and emitted in Cytoscape.js `elements` format. The
build step is a pure function (`build_graph`) so it is unit-testable.

Linking rules (each edge carries a human-readable `reason` for explainability):
  • observed_in  — entity → the evidence clip it was seen in.
  • co_occurs    — two entities seen in the same clip within a time window.
  • Entities with IDENTICAL legible readout text (e.g. a plate) are merged
    into one node across clips, except PERSON, which is never merged: a
    visual match is not an identity assertion, and this system must not make one.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.config import settings

_NODE_TYPE = {
    "PERSON": "Person",
    "VEHICLE": "Vehicle",
    "OBJECT": "Item",
    "ANOMALY": "Item",
    "TEXT_OR_CODE": "Text",
}

_MERGEABLE = {"Vehicle", "Item", "Text"}


def _readout_key(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    key = "".join(ch for ch in text.upper() if ch.isalnum())
    if not key or key == "NONE":
        return None
    return key


def build_graph(
    findings: List[Dict[str, Any]],
    evidence: Dict[str, Dict[str, Any]],
    window_s: float,
) -> Dict[str, Any]:
    """
    findings: dict rows with id, evidence_id, label, category, readout_text,
              confidence, frame_timestamp (seconds), timestamp_str
    evidence: {evidence_id: {file_name, ...}}
    """
    nodes: Dict[str, Dict[str, Any]] = {}
    finding_to_node: Dict[str, str] = {}

    for f in findings:
        ntype = _NODE_TYPE.get(f.get("category") or "OBJECT", "Item")
        key = _readout_key(f.get("readout_text")) if ntype in _MERGEABLE else None
        node_id = f"ent:{ntype}:{key}" if key else f"ent:{f['id']}"

        node = nodes.get(node_id)
        if node is None:
            node = nodes[node_id] = {
                "id": node_id,
                "label": f.get("label") or ntype,
                "node_type": ntype,
                "readout": f.get("readout_text") if key else None,
                "confidence": float(f.get("confidence") or 0.0),
                "finding_ids": [],
                "evidence_ids": [],
                "first_seen": f.get("timestamp_str"),
                "_first_ts": f.get("frame_timestamp") or 0.0,
            }
        node["finding_ids"].append(f["id"])
        if f["evidence_id"] not in node["evidence_ids"]:
            node["evidence_ids"].append(f["evidence_id"])
        node["confidence"] = max(node["confidence"], float(f.get("confidence") or 0.0))
        ts = f.get("frame_timestamp") or 0.0
        if ts < node["_first_ts"]:
            node["_first_ts"], node["first_seen"] = ts, f.get("timestamp_str")
        finding_to_node[f["id"]] = node_id

    elements_nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen_edges: set = set()

    def add_edge(source: str, target: str, relation: str, reason: str, refs: List[str]) -> None:
        a, b = sorted((source, target)) if relation == "co_occurs" else (source, target)
        eid = f"{relation}:{a}:{b}"
        if eid in seen_edges or source == target:
            return
        seen_edges.add(eid)
        edges.append({"data": {
            "id": eid, "source": source, "target": target,
            "relation": relation, "label": relation.replace("_", " "),
            "reason": reason, "source_refs": refs,
        }})

    # Evidence hub nodes + observed_in edges
    used_evidence = {eid for n in nodes.values() for eid in n["evidence_ids"]}
    for eid in sorted(used_evidence):
        info = evidence.get(eid, {})
        elements_nodes.append({"data": {
            "id": f"ev:{eid}", "label": info.get("file_name", eid), "node_type": "Evidence",
            "evidence_ids": [eid], "finding_ids": [], "confidence": None,
        }})
    for n in nodes.values():
        for eid in n["evidence_ids"]:
            add_edge(n["id"], f"ev:{eid}", "observed_in",
                     "Entity was observed in this evidence file.", n["finding_ids"])

    # Temporal co-occurrence inside one clip
    by_ev: Dict[str, List[Dict[str, Any]]] = {}
    for f in findings:
        by_ev.setdefault(f["evidence_id"], []).append(f)
    for items in by_ev.values():
        items.sort(key=lambda r: r.get("frame_timestamp") or 0.0)
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                dt = (b.get("frame_timestamp") or 0.0) - (a.get("frame_timestamp") or 0.0)
                if dt > window_s:
                    break
                add_edge(
                    finding_to_node[a["id"]], finding_to_node[b["id"]], "co_occurs",
                    f"Observed within {dt:.1f}s of each other in the same clip "
                    f"({a.get('timestamp_str')} and {b.get('timestamp_str')}).",
                    [a["id"], b["id"]],
                )

    for n in nodes.values():
        n.pop("_first_ts", None)
        elements_nodes.append({"data": n})

    return {
        "nodes": elements_nodes,
        "edges": edges,
        "meta": {
            "finding_count": len(findings),
            "window_s": window_s,
            "note": "Built from verified findings only. Links are observational, not assertions of identity or involvement.",
        },
    }


async def get_case_graph(case_id: str) -> Dict[str, Any]:
    from backend.database.db import get_db

    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT d.id, d.evidence_id, d.label, d.category, d.readout_text,
                      d.confidence, d.frame_timestamp, d.timestamp_str
               FROM detections d JOIN evidence e ON e.id = d.evidence_id
               WHERE e.case_id = %s AND d.source = 'VLM_ROI'
                 AND d.verification_status = 'Verified'
               ORDER BY d.evidence_id, d.frame_timestamp""",
            (case_id,),
        )
        findings = [dict(r) for r in await cur.fetchall()]

        cur = await db.execute(
            "SELECT id, file_name FROM evidence WHERE case_id = %s", (case_id,)
        )
        evidence = {r["id"]: dict(r) for r in await cur.fetchall()}
        await db.commit()
    finally:
        await db.close()

    return build_graph(findings, evidence, settings.GRAPH_COOCCURRENCE_WINDOW_S)
