"""Tests for clue extraction, cross-evidence correlation, map and report."""

from backend.modules.clue_text import extract_clues, match_key, normalize
from backend.modules.correlation_engine import correlate
from backend.modules.investigation_service import build_clue_graph, build_map
from backend.modules.report_engine import build_report_html

EV = {
    "e1": {"id": "e1", "file_name": "cctv.mp4", "file_type": "VIDEO", "latitude": 13.08, "longitude": 80.27},
    "e2": {"id": "e2", "file_name": "photo.jpg", "file_type": "IMAGE", "latitude": 13.09, "longitude": 80.28},
    "e3": {"id": "e3", "file_name": "notes.pdf", "file_type": "DOCUMENT"},
}


def clue(i, ev, kind, value, conf=0.9, source="AUTO_OCR", ts=None, verified=False):
    return dict(id=i, evidence_id=ev, kind=kind, value=value, norm_value=normalize(kind, value),
                confidence=conf, source=source, timestamp_ms=ts, context="ctx", bbox=None, verified=verified)


# ── extraction ───────────────────────────────────────────────────────────────

def test_extracts_plate_phone_email_amount():
    text = "Car TN 09 AB 1234 left. Call +91 98765 43210 or mail raj.k@example.com. Paid Rs. 4,500."
    kinds = {(c.kind, c.norm) for c in extract_clues(text)}
    assert ("PLATE", "TN09AB1234") in kinds
    assert ("PHONE", "9876543210") in kinds
    assert ("EMAIL", "raj.k@example.com") in kinds
    assert any(k == "AMOUNT" for k, _ in kinds)


def test_plate_formats_normalise_equal():
    a = extract_clues("AB12 CDE")[0]
    b = extract_clues("ab12-cde")[0]
    assert a.kind == b.kind == "PLATE" and a.norm == b.norm == "AB12CDE"


def test_plate_with_ocr_confused_series_is_still_extracted_and_matches():
    # "AB" misread as "A8" must still be recognised as a plate...
    [c] = extract_clues("TN 09 A8 1234")
    assert c.kind == "PLATE" and c.norm == "TN09A81234"
    # ...and correlate with the correctly read plate in another evidence item.
    [m] = correlate([clue("c1", "e1", "PLATE", "TN 09 AB 1234"), clue("c2", "e2", "PLATE", "TN 09 A8 1234")], EV)
    assert m["match_type"] == "OCR_VARIANT"


def test_plain_words_and_short_numbers_are_not_clues():
    assert extract_clues("the quick brown fox 42 jumps") == []


def test_ocr_confusions_share_match_key():
    assert match_key("PLATE", "AB12CDE") == match_key("PLATE", "A812CDE")


# ── correlation ──────────────────────────────────────────────────────────────

def test_exact_plate_match_across_evidence():
    cl = [clue("c1", "e1", "PLATE", "AB12 CDE", ts=2000), clue("c2", "e2", "PLATE", "AB12CDE")]
    [m] = correlate(cl, EV)
    assert m["match_type"] == "EXACT" and m["strength"] == "STRONG"
    assert m["evidence_ids"] == ["e1", "e2"] and m["needs_review"]
    assert {x["timestamp_str"] for x in m["members"]} == {"00:00:02:000", None}


def test_ocr_variant_and_fuzzy_matches():
    [m] = correlate([clue("c1", "e1", "PLATE", "AB12CDE"), clue("c2", "e2", "PLATE", "A812CDE")], EV)
    assert m["match_type"] == "OCR_VARIANT"
    [f] = correlate([clue("c1", "e1", "PLATE", "TN09AB1234"), clue("c2", "e2", "PLATE", "TN09AB1235")], EV)
    assert f["match_type"] == "FUZZY"


def test_same_evidence_twice_is_not_a_match():
    assert correlate([clue("c1", "e1", "PLATE", "AB12CDE"), clue("c2", "e1", "PLATE", "AB12CDE", ts=5)], EV) == []


def test_different_plates_do_not_match():
    assert correlate([clue("c1", "e1", "PLATE", "AB12CDE"), clue("c2", "e2", "PLATE", "ZX99YYY")], EV) == []


def test_appearance_match_is_always_weak():
    cl = [clue("c1", "e1", "OBJECT", "red car", source="AUTO_YOLO"),
          clue("c2", "e2", "OBJECT", "red car", source="AUTO_YOLO")]
    [m] = correlate(cl, EV)
    assert m["match_type"] == "APPEARANCE" and m["strength"] == "WEAK"
    assert "does not establish" in m["explanation"]


def test_low_confidence_cannot_be_strong_and_verified_is_flagged():
    [m] = correlate([clue("c1", "e1", "PHONE", "9876543210", conf=0.2),
                     clue("c2", "e3", "PHONE", "98765 43210", conf=0.2)], EV)
    assert m["strength"] != "STRONG"
    [v] = correlate([clue("c1", "e1", "PLATE", "AB12CDE", verified=True),
                     clue("c2", "e2", "PLATE", "AB12CDE")], EV)
    assert v["verified"] and not v["needs_review"]


# ── map / graph / report ─────────────────────────────────────────────────────

def _matches():
    return correlate([clue("c1", "e1", "PLATE", "AB12CDE", ts=1000), clue("c2", "e2", "PLATE", "AB12CDE"),
                      clue("c3", "e3", "PLATE", "AB12CDE", source="DOCUMENT")], EV)


def test_map_links_located_evidence_and_lists_unlocated():
    mp = build_map({"evidence": list(EV.values())}, _matches())
    assert {p["evidence_id"] for p in mp["points"]} == {"e1", "e2"}
    assert [u["evidence_id"] for u in mp["unlocated"]] == ["e3"]
    assert len(mp["links"]) == 1 and mp["links"][0]["kind"] == "PLATE"


def test_clue_graph_connects_clue_to_each_evidence():
    g = build_clue_graph(_matches(), EV)
    types = [n["data"]["node_type"] for n in g["nodes"]]
    assert types.count("Evidence") == 3 and types.count("Vehicle") == 1
    assert len(g["edges"]) == 3


def test_report_sections_escaping_and_lexicon():
    matches = _matches()
    ctx = {
        "case": {"case_number": "FS-1", "title": "<script>alert(1)</script>", "status": "OPEN"},
        "evidence": list(EV.values()), "matches": matches,
        "findings": [{"evidence_id": "e1", "label": "suspect near blood", "confidence": 0.8,
                      "verification_status": "Verified", "verified_by": "OP", "timestamp_str": "00:00:01:000",
                      "readout_text": "NONE", "crop_sha256": "a" * 64}],
        "auto_detections": [{"evidence_id": "e2", "label": "white car", "confidence": 0.7, "timestamp_str": None}],
        "chain": {"ok": True, "entries_checked": 9, "head_hash": "b" * 64},
    }
    html = build_report_html(ctx)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "suspect" not in html.lower().replace("assistive", "") and "red fluid stain" in html
    for section in ("Matching clues across evidence", "Investigator-verified findings",
                    "Unverified machine observations", "Chain of custody", "Method"):
        assert section in html
    assert "does not establish guilt" in html
