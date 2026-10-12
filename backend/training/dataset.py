"""
backend/training/dataset.py
───────────────────────────
Turn investigator REVIEW decisions into a YOLO fine-tuning dataset.

Every automatic detection can be confirmed, rejected or relabelled in the
Investigation board. Those human decisions are the only trustworthy labels
this system can get, so this module exports them:

  confirmed / relabelled detection  -> a positive box with its class
  rejected detection                -> NOT a box; if its frame has no confirmed
                                       boxes the image is exported with an empty
                                       label file (a hard negative: "nothing
                                       here", which teaches the model to stop
                                       producing that false positive)

Frames come from the preserved evidence files, so the dataset is reproducible
from the case record. Nothing is sent anywhere — export is a local directory.

Pure helpers (`yolo_label_line`, `split_for`) are unit-tested; `export_dataset`
does the I/O.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2

logger = logging.getLogger(__name__)


def yolo_label_line(class_id: int, box_rel: List[float]) -> Optional[str]:
    """[x1,y1,x2,y2] (relative 0-1) -> 'cls cx cy w h'; None if the box is degenerate."""
    x1, y1, x2, y2 = (min(max(float(v), 0.0), 1.0) for v in box_rel)
    w, h = x2 - x1, y2 - y1
    if w <= 0.002 or h <= 0.002:
        return None
    return f"{class_id} {x1 + w / 2:.6f} {y1 + h / 2:.6f} {w:.6f} {h:.6f}"


def split_for(key: str, val_fraction: float = 0.2) -> str:
    """Deterministic train/val assignment from a stable key (reproducible exports)."""
    bucket = int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "val" if bucket < val_fraction else "train"


def _read_frame(path: str, frame_index: int):
    if str(path).lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp")):
        return cv2.imread(path)
    cap = cv2.VideoCapture(path)
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        idx = max(0, min(frame_index, max(total - 1, 0)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        return frame if ok else None
    finally:
        cap.release()


async def fetch_reviewed(case_id: Optional[str] = None) -> List[Dict[str, Any]]:
    from backend.database.db import get_db

    sql = """SELECT d.id, d.evidence_id, d.class_name, d.label, d.bounding_box, d.frame_index,
                    d.verification_status, e.file_path, e.case_id
             FROM detections d JOIN evidence e ON e.id = d.evidence_id
             WHERE d.source = 'AUTO_YOLO' AND d.verification_status IN ('Verified','Rejected')
               AND d.frame_index IS NOT NULL"""
    args: Tuple = ()
    if case_id:
        sql += " AND e.case_id = %s"
        args = (case_id,)
    db = await get_db()
    try:
        cur = await db.execute(sql, args)
        rows = [dict(r) for r in await cur.fetchall()]
        await db.commit()
    finally:
        await db.close()
    return rows


def export_dataset(rows: List[Dict[str, Any]], out_dir: str | Path) -> Dict[str, Any]:
    """Write images/, labels/ and data.yaml under `out_dir`. Returns a summary."""
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True)
        (out / "labels" / split).mkdir(parents=True)

    # Group by frame so a frame's confirmed boxes end up in ONE label file.
    frames: Dict[Tuple[str, int], Dict[str, Any]] = defaultdict(
        lambda: {"path": None, "pos": [], "neg": 0})
    classes: List[str] = []
    for r in rows:
        key = (r["evidence_id"], int(r["frame_index"]))
        fr = frames[key]
        fr["path"] = r["file_path"]
        if r["verification_status"] == "Verified" and (r.get("class_name") or r.get("label")):
            name = (r.get("class_name") or r["label"]).strip().lower()
            if name not in classes:
                classes.append(name)
            box = r["bounding_box"]
            box = json.loads(box) if isinstance(box, str) else box
            fr["pos"].append((name, box))
        else:
            fr["neg"] += 1
    classes.sort()
    index = {c: i for i, c in enumerate(classes)}

    counts = {"train": 0, "val": 0, "positives": 0, "hard_negatives": 0, "skipped": 0}
    for (ev_id, frame_idx), fr in frames.items():
        img = _read_frame(fr["path"], frame_idx)
        if img is None:
            counts["skipped"] += 1
            continue
        lines = [ln for name, box in fr["pos"] if (ln := yolo_label_line(index[name], box))]
        if not lines and not fr["neg"]:
            counts["skipped"] += 1
            continue
        split = split_for(f"{ev_id}:{frame_idx}")
        stem = f"{ev_id[:12]}_{frame_idx:06d}"
        cv2.imwrite(str(out / "images" / split / f"{stem}.jpg"), img)
        (out / "labels" / split / f"{stem}.txt").write_text("\n".join(lines))
        counts[split] += 1
        counts["positives"] += len(lines)
        counts["hard_negatives"] += 0 if lines else 1

    # Ultralytics needs a non-empty val split.
    if counts["val"] == 0 and counts["train"] > 0:
        for p in sorted((out / "images" / "train").glob("*.jpg"))[:1]:
            shutil.copy(p, out / "images" / "val" / p.name)
            shutil.copy(out / "labels" / "train" / f"{p.stem}.txt", out / "labels" / "val" / f"{p.stem}.txt")
            counts["val"] += 1

    names_yaml = "\n".join(f"  {i}: {c}" for i, c in enumerate(classes))
    (out / "data.yaml").write_text(
        f"path: {out.resolve().as_posix()}\ntrain: images/train\nval: images/val\nnames:\n{names_yaml}\n")
    (out / "classes.json").write_text(json.dumps(classes))
    return {"out_dir": str(out), "classes": classes, **counts}
