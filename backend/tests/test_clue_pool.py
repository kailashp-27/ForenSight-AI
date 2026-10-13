"""The unified clue pool: transcripts, PDF text and regional scans all feed correlation."""
import json

from backend.modules.clue_terms import extract_terms, object_key
from backend.modules.correlation_engine import correlate
from backend.modules.investigation_service import _clue_dicts

EVIDENCE = {
    "audio": {"id": "audio", "file_name": "interview.wav", "file_type": "AUDIO"},
    "pdf": {"id": "pdf", "file_name": "statement.pdf", "file_type": "DOCUMENT"},
    "video": {"id": "video", "file_name": "cctv.mp4", "file_type": "VIDEO"},
}


def ctx(chunks=(), detections=(), clues=()):
    return {"clues": list(clues), "chunks": list(chunks), "detections": list(detections),
            "evidence": list(EVIDENCE.values())}


def chunk(cid, ev, text, source="whisper", start=None, page=None):
    return {"id": cid, "evidence_id": ev, "chunk_index": 0, "content": text, "source_type": source,
            "page_number": page, "start_time": start, "end_time": None}


def roi(did, ev, label, category="VEHICLE", readout="NONE", details=(), status="Unverified_Draft"):
    return {"id": did, "evidence_id": ev, "source": "VLM_ROI", "label": label, "category": category,
            "readout_text": readout, "details_json": json.dumps(list(details)), "confidence": 0.8,
            "frame_timestamp": 12.0, "verification_status": status}


def test_names_in_speech_and_pdf_are_matched():
    pool = _clue_dicts(ctx(chunks=[
        chunk("c1", "audio", "I saw Ramesh Kumar near the gate.", start=4.0),
        chunk("c2", "pdf", "Statement of Ramesh Kumar regarding the incident.", source="PDF", page=1),
    ]))
    names = [m for m in correlate(pool, EVIDENCE) if m["kind"] == "NAME"]
    assert len(names) == 1 and names[0]["strength"] == "MEDIUM"     # never STRONG on a name alone
    assert {x["file_name"] for x in names[0]["members"]} == {"interview.wav", "statement.pdf"}


def test_transcript_created_after_analysis_is_still_used():
    # No persisted clue rows at all: everything is derived from the text chunk.
    pool = _clue_dicts(ctx(chunks=[chunk("c1", "audio", "The plate was TN 09 AB 1234.")]))
    assert any(c["kind"] == "PLATE" and c["norm_value"] == "TN09AB1234" and c["source"] == "TRANSCRIPT" for c in pool)


def test_spoken_vehicle_meets_seen_vehicle():
    seen = {"id": "y1", "evidence_id": "video", "kind": "OBJECT", "value": "white car",
            "norm_value": "white car", "confidence": 0.9, "source": "AUTO_YOLO",
            "timestamp_ms": 1000, "bbox": None, "context": "car tracked"}
    pool = _clue_dicts(ctx(chunks=[chunk("c1", "audio", "A white sedan was parked outside.")], clues=[seen]))
    [m] = [m for m in correlate(pool, EVIDENCE) if m["kind"] == "OBJECT"]
    assert m["match_type"] == "APPEARANCE" and m["strength"] == "WEAK"
    assert {x["source"] for x in m["members"]} == {"TRANSCRIPT", "AUTO_YOLO"}


def test_regional_scan_notes_readout_and_label_become_clues():
    pool = _clue_dicts(ctx(detections=[roi(
        "d1", "video", "White van", category="VEHICLE", readout="TN 09 AB 1234",
        details=["Driver named Suresh Babu visible on the door sign"])]))
    kinds = {(c["kind"], c["norm_value"]) for c in pool}
    assert ("OBJECT", "white van") in kinds                      # label
    assert ("PLATE", "TN09AB1234") in kinds                      # readout pattern
    assert ("NAME", "suresh babu") in kinds                      # detail text
    assert all(c["source"] == "VLM_ROI" for c in pool)


def test_regional_scan_plate_matches_transcript_plate():
    pool = _clue_dicts(ctx(
        detections=[roi("d1", "video", "Van", readout="TN09AB1234", status="Verified")],
        chunks=[chunk("c1", "audio", "The number was TN 09 AB 1234, I am sure.")]))
    [m] = [m for m in correlate(pool, EVIDENCE) if m["kind"] == "PLATE"]
    assert m["verified"] is True and len(m["evidence_ids"]) == 2


def test_free_text_readout_is_kept_as_text_clue_and_person_scans_do_not_match_on_looks():
    pool = _clue_dicts(ctx(detections=[
        roi("d1", "video", "Person in dark hoodie", category="PERSON", readout="ANNA STORES")]))
    assert not any(c["kind"] == "OBJECT" for c in pool)         # no appearance clue for people
    assert any(c["kind"] == "TEXT" and c["norm_value"] == "ANNASTORES" for c in pool)


def test_object_key_canonicalisation():
    assert object_key("White sedan") == object_key("white hatchback") == "white car"
    assert object_key("knife-shaped metallic object") == "knife"
    assert [c.value for c in extract_terms("a car came by")] == []        # bare "car" is too generic
