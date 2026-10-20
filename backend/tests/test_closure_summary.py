"""Closure summary: assembled from designations and evidence, never inferred."""
from backend.modules.closure_summary import build_closure_summary

CASE = {"id": "c1", "case_number": "FS-1", "title": "T", "status": "CLOSED"}
FINDINGS = {
    "people": [
        {"key": "p:j-vance", "name": "J.VANCE", "aliases": [], "alias_norms": ["j vance"], "role": "GUILTY",
         "designation": {"basis": "CCTV and badge match", "by": "OP-1", "at": "2026-10-19T14:46:50Z"},
         "identifiers": [], "photos": [], "support": []},
        {"key": "p:a-dent", "name": "Arthur Dent", "role": "VICTIM"},
    ],
    "items": [{"display": "usb", "item_class": "DEVICE", "verified": True, "evidence_count": 2}],
    "vehicles": [], "ids": [],
}
TIMELINE = {"events": [
    {"file_name": "chat.json", "label": "Chat", "time": "01:10", "offset_ms": 10, "text": "Vance entered the server room"},
    {"file_name": "cctv.mp4", "label": "Video", "time": "01:34", "offset_ms": 20, "text": "someone leaves with a bag"},
]}


def test_guilty_comes_from_the_investigator_with_basis_and_author():
    out = build_closure_summary(CASE, FINDINGS, TIMELINE, {})
    g = out["guilty"][0]
    assert g["name"] == "J.VANCE" and g["designated_by"] == "OP-1" and g["basis"] == "CCTV and badge match"
    assert [e["file_name"] for e in g["what_the_evidence_shows"]] == ["chat.json"]   # only text that names them
    assert out["others"]["victims"][0]["name"] == "Arthur Dent"
    assert [e["time"] for e in out["sequence"]] == ["01:10", "01:34"]


def test_no_guilty_designation_is_flagged_not_guessed():
    findings = {**FINDINGS, "people": [{"key": "p:x", "name": "X", "role": "SUSPECT"}]}
    out = build_closure_summary(CASE, findings, TIMELINE, {})
    assert out["guilty"] == [] and out["notes"]
