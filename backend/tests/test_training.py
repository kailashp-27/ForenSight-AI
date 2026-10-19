"""Dataset export for fine-tuning (pure helpers + a real on-disk export)."""
import json

import cv2
import numpy as np

from backend.training.dataset import export_dataset, split_for, yolo_label_line


def test_yolo_label_line_converts_corners_to_centre_format():
    line = yolo_label_line(2, [0.1, 0.2, 0.5, 0.6])
    cls, cx, cy, w, h = line.split()
    assert cls == "2"
    assert (float(cx), float(cy), float(w), float(h)) == (0.3, 0.4, 0.4, 0.4)


def test_degenerate_boxes_are_dropped():
    assert yolo_label_line(0, [0.5, 0.5, 0.5, 0.9]) is None
    assert yolo_label_line(0, [0.5, 0.5, 0.9, 0.5]) is None


def test_split_is_deterministic_and_roughly_balanced():
    assert split_for("a:1") == split_for("a:1")
    vals = sum(split_for(f"ev:{i}") == "val" for i in range(500))
    assert 60 < vals < 140          # ~20 %


def test_export_writes_positives_and_hard_negatives(tmp_path):
    img = tmp_path / "scene.jpg"
    cv2.imwrite(str(img), np.full((100, 200, 3), 120, np.uint8))
    rows = [
        # frame 0: one confirmed + one rejected box -> only the confirmed one is a label
        {"evidence_id": "evA", "frame_index": 0, "file_path": str(img), "class_name": "person",
         "label": "dark person", "bounding_box": json.dumps([0.1, 0.1, 0.4, 0.9]), "verification_status": "Verified"},
        {"evidence_id": "evA", "frame_index": 0, "file_path": str(img), "class_name": "car",
         "label": "red car", "bounding_box": json.dumps([0.5, 0.5, 0.9, 0.9]), "verification_status": "Rejected"},
        # frame 1: only a rejected box -> exported as an image with an EMPTY label file
        {"evidence_id": "evB", "frame_index": 0, "file_path": str(img), "class_name": "car",
         "label": "white car", "bounding_box": json.dumps([0.2, 0.2, 0.6, 0.6]), "verification_status": "Rejected"},
    ]
    out = tmp_path / "ds"
    summary = export_dataset(rows, out)

    assert summary["classes"] == ["person"]
    assert summary["positives"] == 1 and summary["hard_negatives"] == 1
    assert (out / "data.yaml").exists()
    label_files = list((out / "labels").rglob("*.txt"))
    contents = sorted(p.read_text().strip() for p in label_files if "val" not in p.parts or True)
    assert any(c.startswith("0 ") for c in contents)          # the confirmed person
    assert any(c == "" for c in contents)                     # the hard negative
    assert len(list((out / "images" / "val").glob("*.jpg"))) >= 1   # val never empty
