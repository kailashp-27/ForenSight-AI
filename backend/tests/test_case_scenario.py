"""
End-to-end scenario test: the "Operation: Midnight Drop" style case.

Evidence: Slack export, voicemail transcript, CCTV clip (burned-in clock),
scanned PDF, photo. Verifies the four connections an investigator expects.
"""
import json

import pytest

from backend.modules.case_summary import build_key_findings
from backend.modules.correlation_engine import correlate
from backend.modules.event_timeline import build_event_timeline
from backend.modules.investigation_service import _clue_dicts, chunk_terms

EV = [
    {"id": "slack", "file_name": "slack_export.json", "file_type": "TEXT"},
    {"id": "voice", "file_name": "voicemail.mp3", "file_type": "AUDIO", "recording_start": None},
    {"id": "cctv", "file_name": "cctv_cam4.mp4", "file_type": "VIDEO", "recording_start": "2026-10-11T01:33:40"},
    {"id": "pdf", "file_name": "trash_scrap.pdf", "file_type": "DOCUMENT"},
    {"id": "photo", "file_name": "img.png", "file_type": "IMAGE"},
]


def chunk(i, ev, text, source, **kw):
    return {"id": f"c{i}", "evidence_id": ev, "chunk_index": i, "content": text, "source_type": source,
            "page_number": kw.get("page"), "start_time": kw.get("start"), "end_time": None,
            "wall_time": kw.get("wall"), "speaker": kw.get("speaker")}


def roi(i, label, category, readout, details, ts, role=None, name=None, status="Verified"):
    return {"id": f"r{i}", "evidence_id": "cctv", "source": "VLM_ROI", "label": label, "category": category,
            "readout_text": readout, "details_json": json.dumps(details), "confidence": 0.85,
            "frame_timestamp": ts, "timestamp_str": f"00:00:{int(ts):02d}:000", "verification_status": status,
            "role": role, "subject_name": name, "frame_index": int(ts * 25), "bounding_box": "[1,2,30,40]"}


@pytest.fixture(scope="module")
def case():
    chunks = [
        chunk(1, "slack", "Maintenance window is at 1:00 AM. Sector 4 will be empty.", "CHAT",
              speaker="j.vance", wall="2026-10-11T00:41:00"),
        chunk(2, "slack", "ok. bring the silver drive to the south dock", "CHAT",
              speaker="m.cole", wall="2026-10-11T00:43:00"),
        chunk(3, "slack", "The white van will wait there.", "CHAT", speaker="j.vance", wall="2026-10-11T00:44:00"),
        chunk(4, "voice", "Sector 4 is supposed to be empty.", "whisper", start=9.0),
        chunk(5, "voice", "Just stay out of sight until the maintenance window is over. Got the silver drive.",
              "whisper", start=14.0),
        chunk(6, "pdf", "Apex Dynamics - Visitor Sign-in Log\nLocation: Sector 4 Cooling Units\n"
                        "Wait at South Dock. Plate: Tx-882-V. Visitor pass: V-4471", "PDF_OCR", page=1),
    ]
    detections = [
        roi(1, "Visitor", "TEXT_OR_CODE", "J.VANCE Tier 2",
            ["The badge is made of clear plastic."], 2.9, role="SUSPECT", name="J. Vance"),
        roi(2, "usb", "OBJECT", "NONE", ["black", "rectangular", "metallic silver usb drive"], 6.5, role="STOLEN"),
        roi(3, "readout_text", "TEXT_OR_CODE", "TX-88-2",
            ["The text is located on a vehicle's license plate."], 9.7, role="PLATE"),
        roi(4, "White van", "VEHICLE", "NONE", ["white van parked at the dock"], 9.7, role="VEHICLE"),
    ]
    ctx = {"clues": [], "chunks": chunks, "detections": detections, "evidence": EV,
           "case": {"case_number": "FS-1", "title": "Midnight Drop"}}
    pool = _clue_dicts(ctx)
    evidence = {e["id"]: e for e in EV}
    matches = correlate(pool, evidence)
    return {"ctx": ctx, "pool": pool, "matches": matches}


def files(m):
    return {x["file_name"] for x in m["members"]}


def test_1_person_name_links_chat_author_to_badge_scan(case):
    names = [m for m in case["matches"] if m["kind"] == "NAME"]
    vance = [m for m in names if "vance" in m["value"].lower()]
    assert vance, [(m["kind"], m["value"]) for m in case["matches"]]
    assert {"slack_export.json", "cctv_cam4.mp4"} <= files(vance[0])


def test_2_partial_plate_links_scan_to_pdf(case):
    plates = [m for m in case["matches"] if m["kind"] == "PLATE"]
    assert plates and {"cctv_cam4.mp4", "trash_scrap.pdf"} <= files(plates[0])
    assert plates[0]["strength"] in ("MEDIUM", "STRONG")


def test_3_silver_drive_links_speech_chat_and_scan(case):
    drive = [m for m in case["matches"] if m["kind"] == "OBJECT" and "usb drive" in m["id"].lower()
             or (m["kind"] == "OBJECT" and any("drive" in x["value"].lower() or "usb" in x["value"].lower()
                                              for x in m["members"]))]
    assert drive, [(m["kind"], m["value"], files(m)) for m in case["matches"]]
    assert {"slack_export.json", "voicemail.mp3", "cctv_cam4.mp4"} <= files(drive[0])


def test_4_timeline_aligns_chat_mention_audio_sector_and_video_clock(case):
    tl = build_event_timeline(case["ctx"], chunk_terms, window_min=60)
    # the video's burned-in clock puts the usb scan at ~01:33:46 on the same clock as the 1:00 AM mention
    scan = [e for e in tl["events"] if e["kind"] == "scan" and "usb" in e["text"].lower()]
    assert scan and scan[0]["time"].startswith("2026-10-11T01:34") or scan[0]["time"].startswith("2026-10-11T01:33")
    mention = [e for e in tl["events"] if e["kind"] == "mention" and "1:00" in e["label"]]
    assert mention and mention[0]["time"].startswith("2026-10-11T01:00")
    # one aligned group links the Slack text, the voicemail (by 'Sector 4') and the CCTV frames
    grp = [g for g in tl["groups"] if {"slack", "cctv", "voice"} <= set(g["evidence_ids"])]
    assert grp, tl["groups"]
    assert any(t["value"].lower().startswith("sector") for t in grp[0]["shared_terms"])


def test_key_findings_people_ids_items_vehicle(case):
    kf = build_key_findings(case["ctx"], case["pool"], case["matches"])

    vance = next(p for p in kf["people"] if "vance" in p["name"].lower())
    assert vance["role"] == "SUSPECT" and vance["role_source"] == "investigator" and vance["verified"]
    assert vance["photos"] and vance["photos"][0]["url"].endswith("/findings/r1/crop")

    assert any("4471" in i["value"] for i in kf["ids"])

    usb = next(i for i in kf["items"] if i["name"] == "usb drive")
    assert usb["item_class"] == "DEVICE" and usb["evidence_count"] >= 3 and usb["photos"]

    veh = next(v for v in kf["vehicles"] if "van" in v["display"].lower() or v["description"].endswith("truck"))
    assert veh["plates"] and "TX882" in veh["plates"][0]["plate"].upper().replace("-", "")
