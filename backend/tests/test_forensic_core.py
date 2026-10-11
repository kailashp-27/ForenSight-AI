"""
Tests for the forensic ROI-inspection core (no MySQL / Ollama required).

Run from the repository root:
    python -m pytest backend/tests -q
"""

import asyncio
import json

import cv2
import numpy as np
import pytest
from pydantic import ValidationError

from backend.modules import audit_engine
from backend.modules.graph_engine import build_graph
from backend.modules.vision import cv_engine
from backend.modules.vision.objective_lexicon import enforce_objective_lexicon
from backend.modules.vision import vlm_client
from backend.schemas import VLMScanRequest


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def sample_video(tmp_path):
    """A 40-frame, 10 fps, 320x240 clip with a white square that moves right."""
    path = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (320, 240))
    for i in range(40):
        frame = np.full((240, 320, 3), 40, dtype=np.uint8)
        cv2.rectangle(frame, (10 + i * 5, 80), (50 + i * 5, 120), (255, 255, 255), -1)
        writer.write(frame)
    writer.release()
    return path


# ── objective lexicon ────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected_fragment", [
    ("blood on the floor", "red fluid stain"),
    ("a murder weapon on the table", "metallic tool"),
    ("the suspect wearing a hoodie", "person"),
])
def test_lexicon_rewrites_subjective_terms(raw, expected_fragment):
    clean, compliant = enforce_objective_lexicon(raw)
    assert expected_fragment in clean
    assert compliant is False


def test_lexicon_removes_legal_characterization():
    clean, compliant = enforce_objective_lexicon("clearly guilty of robbery")
    assert "guilty" not in clean.lower() and "robbery" not in clean.lower()
    assert not compliant


def test_lexicon_passes_neutral_text_unchanged():
    text = "person in dark hoodie near red fluid stain"
    assert enforce_objective_lexicon(text) == (text, True)


# ── cv engine ────────────────────────────────────────────────────────────────

def test_timestamp_format():
    assert cv_engine.format_timestamp(3_723_456) == "01:02:03:456"
    assert cv_engine.format_timestamp(0) == "00:00:00:000"


def test_probe_and_exact_frame(sample_video):
    probe = cv_engine.probe_video(sample_video)
    assert (probe.width, probe.height, probe.frame_count) == (320, 240, 40)
    frame, info, _ = cv_engine.extract_frame(sample_video, timestamp_ms=1000)
    assert info.index == 10 and info.timestamp_str == "00:00:01:000"
    assert frame.shape == (240, 320, 3)


def test_frame_index_clamped_at_end_not_error(sample_video):
    # A scrubber dragged to its max lands on frame_count (one past the end).
    _, info, probe = cv_engine.extract_frame(sample_video, frame_index=40)
    assert info.index == probe.frame_count - 1


def test_extract_requires_exactly_one_position(sample_video):
    with pytest.raises(ValueError):
        cv_engine.extract_frame(sample_video)
    with pytest.raises(ValueError):
        cv_engine.extract_frame(sample_video, frame_index=1, timestamp_ms=1)


def test_missing_video_raises():
    with pytest.raises(cv_engine.VideoError):
        cv_engine.probe_video("does-not-exist.mp4")


def test_roi_patch_is_448_and_hashed(sample_video):
    frame, _, _ = cv_engine.extract_frame(sample_video, frame_index=5)
    roi = cv_engine.relative_to_pixels(0.1, 0.3, 0.4, 0.55, 320, 240)
    patch = cv_engine.prepare_roi_patch(frame, roi)
    assert patch.patch_bgr.shape == (448, 448, 3)
    assert len(patch.frame_sha256) == 64 and len(patch.crop_sha256) == 64
    # 10% context padding must widen the crop beyond the drawn box
    assert patch.crop_box_px[0] <= roi[0] and patch.crop_box_px[2] >= roi[2]
    # deterministic: same input → same hashes (chain-of-custody reproducibility)
    again = cv_engine.prepare_roi_patch(frame, roi)
    assert again.crop_sha256 == patch.crop_sha256


def test_roi_zero_area_rejected(sample_video):
    frame, _, _ = cv_engine.extract_frame(sample_video, frame_index=0)
    with pytest.raises(ValueError):
        cv_engine.prepare_roi_patch(frame, [50, 50, 50, 90])


def test_relative_to_pixels_orders_and_clamps():
    assert cv_engine.relative_to_pixels(0.9, 0.9, 0.1, 0.1, 100, 200) == [10, 20, 90, 180]


# ── schemas ──────────────────────────────────────────────────────────────────

def test_scan_request_requires_exactly_one_position():
    base = dict(video_id="v", x1=0.1, y1=0.1, x2=0.5, y2=0.5)
    with pytest.raises(ValidationError):
        VLMScanRequest(**base)
    with pytest.raises(ValidationError):
        VLMScanRequest(**base, frame_offset=1, timestamp_ms=1)
    assert VLMScanRequest(**base, timestamp_ms=500).timestamp_ms == 500


def test_scan_request_normalises_reversed_box_and_rejects_tiny():
    req = VLMScanRequest(video_id="v", timestamp_ms=0, x1=0.8, y1=0.8, x2=0.2, y2=0.2)
    assert (req.x1, req.y1, req.x2, req.y2) == (0.2, 0.2, 0.8, 0.8)
    with pytest.raises(ValidationError):
        VLMScanRequest(video_id="v", timestamp_ms=0, x1=0.5, y1=0.5, x2=0.501, y2=0.9)


# ── VLM client ───────────────────────────────────────────────────────────────

def test_vlm_refuses_non_local_endpoint():
    with pytest.raises(ValueError):
        vlm_client.VLMClient(base_url="http://10.0.0.5:11434")
    with pytest.raises(ValueError):
        vlm_client.VLMClient(base_url="https://api.example.com")


def test_vlm_output_normalised_and_lexicon_applied():
    raw = json.dumps({
        "label": "Suspect near vehicle", "category": "person",
        "readout_text": "NONE", "details": ["blood on sleeve", "a", "b", "c-extra"],
        "confidence_score": 87,
    })
    res = vlm_client.parse_model_output(raw)
    assert res.category == "PERSON"
    assert res.confidence_score == pytest.approx(0.87)
    assert "suspect" not in res.label.lower()
    assert "red fluid stain" in res.details[0]
    assert len(res.details) == 3
    assert res.objective_lexicon_compliant is False


@pytest.mark.parametrize("raw", [
    "not json at all",
    json.dumps({"label": "x", "category": "WEAPON", "readout_text": "NONE", "details": [], "confidence_score": 0.5}),
    json.dumps({"category": "OBJECT", "readout_text": "NONE", "details": [], "confidence_score": 0.5}),
])
def test_vlm_invalid_output_rejected(raw):
    with pytest.raises(vlm_client.VLMOutputError):
        vlm_client.parse_model_output(raw)


def test_vlm_unreachable_maps_to_unavailable(monkeypatch):
    import httpx

    async def boom(self, *a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx.AsyncClient, "post", boom)
    client = vlm_client.VLMClient(base_url="http://127.0.0.1:11434")
    with pytest.raises(vlm_client.VLMUnavailableError):
        asyncio.run(client.analyze_patch("AAAA"))


def test_vlm_request_is_schema_constrained_and_deterministic(monkeypatch):
    import httpx
    captured = {}

    class FakeResp:
        status_code = 200
        text = ""
        def raise_for_status(self): ...
        def json(self):
            return {"response": json.dumps({
                "label": "Dark sedan", "category": "VEHICLE", "readout_text": "AB12 CDE",
                "details": ["four doors"], "confidence_score": 0.9})}

    async def fake_post(self, url, json=None, **k):
        captured["url"], captured["payload"] = url, json
        return FakeResp()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    out = asyncio.run(vlm_client.VLMClient(base_url="http://localhost:11434").analyze_patch("AAAA"))
    p = captured["payload"]
    assert captured["url"].endswith("/api/generate")
    assert p["options"]["temperature"] == 0.0 and p["options"]["num_predict"] == 250
    assert isinstance(p["format"], dict) and "properties" in p["format"]
    assert out.result.readout_text == "AB12 CDE" and out.result.objective_lexicon_compliant


# ── audit chain ──────────────────────────────────────────────────────────────

def _chain(n=4):
    rows, prev = [], audit_engine.GENESIS_HASH
    for i in range(1, n + 1):
        meta = audit_engine.canonical_json({"i": i})
        ts = f"2026-01-01T00:00:0{i}.000000Z"
        h = audit_engine.compute_entry_hash(prev, "c1", "e1", None, "OP", f"ACT{i}", ts, meta)
        rows.append(dict(seq=i, case_id="c1", evidence_id="e1", file_hash_sha256=None,
                         operator_id="OP", action=f"ACT{i}", timestamp_utc=ts,
                         metadata_json=meta, prev_hash=prev, entry_hash=h))
        prev = h
    return rows


def test_chain_verifies_when_intact():
    rows = _chain()
    rep = audit_engine.verify_rows(rows, expected_head_hash=rows[-1]["entry_hash"])
    assert rep.ok and rep.entries_checked == 4


def test_chain_detects_modified_row():
    rows = _chain()
    rows[1]["operator_id"] = "SOMEONE_ELSE"
    rep = audit_engine.verify_rows(rows)
    assert not rep.ok and rep.broken_at_seq == 2


def test_chain_detects_deleted_middle_row():
    rows = _chain()
    del rows[1]
    rep = audit_engine.verify_rows(rows)
    assert not rep.ok and rep.broken_at_seq == 3


def test_chain_detects_truncated_tail_via_head():
    rows = _chain()
    head = rows[-1]["entry_hash"]
    rep = audit_engine.verify_rows(rows[:-1], expected_head_hash=head)
    assert not rep.ok


def test_payload_encryption_roundtrip_and_aad_binding(tmp_path, monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "AUDIT_KEY_PATH", str(tmp_path / "k.key"))
    monkeypatch.setattr(audit_engine, "_key_cache", None)
    blob = audit_engine.encrypt_payload('{"label":"x"}', aad="ev:frame")
    assert "label" not in json.dumps(blob)
    assert audit_engine.decrypt_payload(blob) == '{"label":"x"}'
    blob["aad"] = "other"
    with pytest.raises(Exception):
        audit_engine.decrypt_payload(blob)


# ── graph ────────────────────────────────────────────────────────────────────

def _f(fid, ev, cat, text, ts, label="obj"):
    return dict(id=fid, evidence_id=ev, label=label, category=cat, readout_text=text,
                confidence=0.8, frame_timestamp=ts, timestamp_str=f"t{ts}")


def test_graph_merges_identical_plate_across_clips_but_never_persons():
    findings = [
        _f("a", "e1", "VEHICLE", "AB12 CDE", 1.0, "sedan"),
        _f("b", "e2", "VEHICLE", "ab12cde", 5.0, "sedan"),
        _f("c", "e1", "PERSON", "NONE", 2.0, "person"),
        _f("d", "e2", "PERSON", "NONE", 6.0, "person"),
    ]
    g = build_graph(findings, {"e1": {"file_name": "a.mp4"}, "e2": {"file_name": "b.mp4"}}, 10.0)
    entity_nodes = [n["data"] for n in g["nodes"] if n["data"]["node_type"] != "Evidence"]
    vehicles = [n for n in entity_nodes if n["node_type"] == "Vehicle"]
    persons = [n for n in entity_nodes if n["node_type"] == "Person"]
    assert len(vehicles) == 1 and len(vehicles[0]["finding_ids"]) == 2
    assert len(persons) == 2          # persons are never merged on appearance


def test_graph_cooccurrence_respects_window():
    findings = [_f("a", "e1", "OBJECT", "NONE", 0.0), _f("b", "e1", "PERSON", "NONE", 4.0),
                _f("c", "e1", "VEHICLE", "NONE", 60.0)]
    g = build_graph(findings, {"e1": {"file_name": "a.mp4"}}, 10.0)
    co = [e["data"] for e in g["edges"] if e["data"]["relation"] == "co_occurs"]
    assert len(co) == 1 and set(co[0]["source_refs"]) == {"a", "b"}
    assert all(e["data"]["reason"] for e in g["edges"])
