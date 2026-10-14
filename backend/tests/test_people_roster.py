"""People roster: names, badges / ID cards and investigator designations."""
import json

import pytest
from fastapi import HTTPException

from backend.modules.correlation_engine import correlate
from backend.modules.investigation_service import _apply_aliases, _clue_dicts
from backend.modules.people_roster import build_roster
from backend.modules.report_engine import build_report_html
from backend.routes.investigation import PersonDesignationBody

EV = [
    {"id": "chat", "file_name": "slack.json", "file_type": "TEXT"},
    {"id": "cctv", "file_name": "cctv.mp4", "file_type": "VIDEO"},
    {"id": "pdf", "file_name": "log.pdf", "file_type": "DOCUMENT"},
]


def chunk(i, ev, text, source, **kw):
    return {"id": f"c{i}", "evidence_id": ev, "chunk_index": i, "content": text, "source_type": source,
            "page_number": kw.get("page"), "start_time": None, "end_time": None,
            "wall_time": kw.get("wall"), "speaker": kw.get("speaker")}


def roi(i, readout, details=(), **kw):
    return {"id": i, "evidence_id": "cctv", "source": "VLM_ROI", "label": kw.get("label", "Visitor"),
            "category": "TEXT_OR_CODE", "readout_text": readout, "details_json": json.dumps(list(details)),
            "confidence": 0.8, "frame_timestamp": 3.0, "timestamp_str": "00:00:03:000",
            "verification_status": "Verified", "role": kw.get("role"), "subject_name": kw.get("name")}


def roster(chunks=(), dets=(), designs=()):
    ctx = {"clues": [], "chunks": list(chunks), "detections": list(dets), "evidence": EV,
           "designations": list(designs)}
    pool = _clue_dicts(ctx)
    _apply_aliases(pool, ctx["designations"])
    return build_roster(ctx, pool, correlate(pool, {e["id"]: e for e in EV}), ctx["designations"])


def find(r, token):
    return next(p for p in r if token in p["name"].lower() or any(token in a.lower() for a in p["aliases"]))


def test_people_come_from_names_chat_authors_and_badges():
    r = roster(
        chunks=[chunk(1, "chat", "Window opens at 1 AM.", "CHAT", speaker="j.vance"),
                chunk(2, "pdf", "Statement by Ramesh Kumar about the incident.", "PDF", page=1)],
        dets=[roi("r1", "J.VANCE Tier 2")])
    vance = find(r, "vance")
    assert vance["evidence_count"] == 2 and vance["photos"]                    # chat author + badge scan merged
    assert any("VANCE" in i["value"].upper() for i in vance["identifiers"])    # the badge text is attached
    assert find(r, "ramesh")["role"] is None                                   # nothing assigned automatically


def test_unattached_badge_becomes_an_unidentified_holder_entry():
    r = roster(chunks=[chunk(1, "pdf", "Visitor pass: V-4471 issued at the gate.", "PDF_OCR", page=1)])
    holder = [p for p in r if p.get("unidentified")]
    assert holder and holder[0]["identifiers"][0]["value"].upper() == "V-4471"
    assert holder[0]["name"].startswith("Holder of")


def test_system_suggests_only_victim_suspect_witness_and_never_guilty():
    r = roster(chunks=[chunk(1, "pdf", "The suspect Mr Iqbal ran from the yard. Victim Priya Nair was shaken.", "PDF")])
    sus = find(r, "iqbal")
    assert sus["role"] is None and sus["suggested_role"] == "SUSPECT" and "suspect" in sus["suggested_reason"]
    assert find(r, "priya")["suggested_role"] == "VICTIM"
    assert all(p["suggested_role"] in (None, "VICTIM", "SUSPECT", "WITNESS") for p in r)
    assert all(p["role"] != "GUILTY" for p in r)


def test_investigator_designation_wins_and_alias_merges_a_second_name():
    designs = [{"person_key": "p:j-vance", "display_name": "J. Vance", "role": "SUSPECT", "basis": "badge on CCTV",
                "aliases": json.dumps(["jv_ops", "V-4471"]), "is_manual": 0, "designated_by": "OP-7",
                "designated_at": "2026-10-14T10:00:00Z"}]
    r = roster(chunks=[chunk(1, "chat", "meet at dock", "CHAT", speaker="jv_ops"),
                       chunk(2, "pdf", "Visitor pass: V-4471", "PDF")],
               dets=[roi("r1", "J.VANCE Tier 2")], designs=designs)
    p = find(r, "vance")
    assert p["role"] == "SUSPECT" and p["role_source"] == "investigator designation"
    assert p["designation"]["by"] == "OP-7" and p["evidence_count"] >= 2        # jv_ops merged in
    assert any(i["norm"] == "V4471" for i in p["identifiers"])                  # ID attached by the investigator


def test_manual_person_with_no_evidence_still_listed():
    designs = [{"person_key": "p:mia-cole", "display_name": "Mia Cole", "role": "VICTIM", "basis": None,
                "aliases": "[]", "is_manual": 1, "designated_by": "OP-1", "designated_at": "2026-10-14T10:00:00Z"}]
    r = roster(designs=designs)
    assert len(r) == 1 and r[0]["name"] == "Mia Cole" and r[0]["manual"] and r[0]["role"] == "VICTIM"


def test_report_attributes_a_guilty_designation_to_the_investigator():
    designs = [{"person_key": "p:j-vance", "display_name": "J. Vance", "role": "GUILTY",
                "basis": "Badge on CCTV, named in chat and in the visitor log.", "aliases": "[]", "is_manual": 0,
                "designated_by": "OP-7", "designated_at": "2026-10-14T10:00:00Z"}]
    r = roster(chunks=[chunk(1, "chat", "hello", "CHAT", speaker="j.vance")], designs=designs)
    html = build_report_html({"case": {"case_number": "FS-1", "title": "t"}, "evidence": EV, "matches": [],
                              "people": r})
    assert "Guilty (investigator&#x27;s determination)" in html or "Guilty (investigator's determination)" in html
    assert "OP-7" in html and "not a finding of this system" in html


# ── the guilty designation is deliberately hard to set ───────────────────────

def body(**kw):
    base = dict(role="GUILTY", operator_id="OP-7", basis="Badge on CCTV, named in chat and in the visitor log.",
                confirm_determination=True)
    base.update(kw)
    return PersonDesignationBody(**base)


def test_guilty_requires_explicit_confirmation():
    with pytest.raises(HTTPException) as e:
        body(confirm_determination=False).check()
    assert e.value.status_code == 422 and "your determination" in e.value.detail.lower()


def test_guilty_requires_a_written_basis():
    for bad in (None, "", "short"):
        with pytest.raises(HTTPException):
            body(basis=bad).check()


def test_valid_guilty_and_other_roles_pass_and_unknown_role_rejected():
    body().check()
    body(role="SUSPECT", confirm_determination=False, basis=None).check()
    with pytest.raises(HTTPException):
        body(role="EXECUTED").check()


def test_case_reference_is_not_attached_to_people_as_an_id_card():
    text = ("WITNESS STATEMENT CASE FS-2026-001. I, Ramesh Kumar, saw a van. "
            "The driver, Suresh Babu, got out. " + "filler text " * 12 + "Visitor pass: V-4471 issued to Mia Cole.")
    r = roster(chunks=[chunk(1, "pdf", text, "PDF", page=1)])
    for p in r:
        assert not any("FS2026001" in i["norm"] for i in p["identifiers"]), p["name"]
    ramesh, suresh = find(r, "ramesh"), find(r, "suresh")
    assert not ramesh["identifiers"] and not suresh["identifiers"]
    mia = find(r, "mia")
    assert any(i["norm"] == "V4471" for i in mia["identifiers"])      # the pass next to her name does attach
