"""
backend/modules/video_pipeline.py
─────────────────────────────────
Tracking-based video analysis (replaces fixed-interval per-frame sampling).

  1. Decode the clip once; run detection + multi-object tracking (ByteTrack)
     at AUTO_DETECT_FPS, so one physical object = ONE track, not hundreds of
     per-frame duplicates.
  2. Optionally run an open-vocabulary detector (YOLO-World) for forensic
     classes COCO lacks (license plate, knife, backpack, helmet, ...).
  3. For every track keep its few sharpest / largest crops; vote class and
     colour across the whole track instead of trusting one frame.
  4. OCR only those best crops (vehicles: plate-region + whole vehicle,
     upscaled) plus sparse full-frame scene text.
  5. Pool every plate read across tracks/frames, cluster reads of the same
     plate, then format-correct + confidence-vote each cluster
     (plate_postprocess).

Why this is more accurate than per-frame OCR: errors are random per frame, so
voting removes them; crops are the sharpest available; and format rules fix
the systematic OCR confusions (O/0, B/8 ...).
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend.config import settings
from backend.modules import auto_analysis as A
from backend.modules.clue_text import extract_clues
from backend.modules.plate_postprocess import cluster_reads, vote

logger = logging.getLogger(__name__)

PLATE_CLASS = "license plate"
CROP_PAD = 0.10
MAX_CROP_SIDE = 480


@dataclass
class _Track:
    key: str
    source: str                                    # coco | openvocab
    cls_votes: Counter = field(default_factory=Counter)
    color_votes: Counter = field(default_factory=Counter)
    first_ms: int = 0
    last_ms: int = 0
    frames: int = 0
    max_conf: float = 0.0
    best_frame: int = 0
    best_bbox_rel: List[float] = field(default_factory=lambda: [0, 0, 1, 1])
    crops: List[Tuple[float, np.ndarray, int]] = field(default_factory=list)  # (quality, bgr, frame)

    @property
    def cls(self) -> str:
        return self.cls_votes.most_common(1)[0][0] if self.cls_votes else "object"

    @property
    def color(self) -> str:
        return self.color_votes.most_common(1)[0][0] if self.color_votes else "unknown"


def _iou(a: List[int], b: List[int]) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _quality(crop: np.ndarray, conf: float, frame_area: float) -> float:
    """Higher = better crop for OCR/inspection: big, confident and sharp."""
    h, w = crop.shape[:2]
    if h < 8 or w < 8:
        return 0.0
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    size = (h * w / frame_area) ** 0.5
    return conf * (0.3 + size) * (sharp / (sharp + 60.0))


def _padded_crop(frame: np.ndarray, box: List[int]) -> np.ndarray:
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = box
    px, py = int((x2 - x1) * CROP_PAD), int((y2 - y1) * CROP_PAD)
    crop = frame[max(0, y1 - py): min(h, y2 + py), max(0, x1 - px): min(w, x2 + px)]
    side = max(crop.shape[:2])
    if side > MAX_CROP_SIDE:
        s = MAX_CROP_SIDE / side
        crop = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return crop.copy()


def _upscale(img: np.ndarray, target_w: int) -> np.ndarray:
    h, w = img.shape[:2]
    if w >= target_w or w == 0:
        return img
    s = min(4.0, target_w / w)
    return cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)


def _plate_reads_from_texts(texts: List[A.FrameText]) -> List[Tuple[str, float, List[int]]]:
    """Extract plate candidates from OCR lines and from lines joined together."""
    out: List[Tuple[str, float, List[int]]] = []
    seen = set()
    for t in texts:
        for c in extract_clues(t.text):
            if c.kind == "PLATE" and (c.norm, t.bbox_px[0]) not in seen:
                seen.add((c.norm, t.bbox_px[0]))
                out.append((c.norm, t.conf, t.bbox_px))
    # Plates are often split across lines ("TN 09" / "AB 1234"): join the lines of
    # each engine separately so two engines' duplicates never get concatenated.
    for engine in {t.engine for t in texts}:
        group = [t for t in texts if t.engine == engine]
        if len(group) < 2:
            continue
        joined = " ".join(t.text for t in sorted(group, key=lambda t: (t.bbox_px[1] // 20, t.bbox_px[0])))
        conf = sum(t.conf for t in group) / len(group)
        for c in extract_clues(joined):
            if c.kind == "PLATE" and (c.norm, engine) not in seen:
                seen.add((c.norm, engine))
                out.append((c.norm, conf, group[0].bbox_px))
    return out


def analyze_video(path: str | Path,
                  progress: Optional[Callable[[int, int], None]] = None) -> A.AnalysisResult:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError("OpenCV could not open the video")

    result = A.AnalysisResult(kind="VIDEO", method="tracking+voting")
    detector = A._get_detector()
    world = A._get_world()
    if detector is None:
        result.warnings.append("Object detector unavailable; objects not analysed.")
    if A._get_ocr() is None:
        result.warnings.append("OCR unavailable; on-screen text not analysed.")
    if settings.OPEN_VOCAB_ENABLED and world is None:
        result.warnings.append("Open-vocabulary detector unavailable; only COCO classes were used.")

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 25.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_area = float(max(1, w * h))
        result.duration_ms = int(total / fps * 1000) if total else 0

        det_stride = max(1, round(fps / settings.AUTO_DETECT_FPS))
        if total and total / det_stride > settings.AUTO_MAX_DETECT_FRAMES:
            det_stride = int(np.ceil(total / settings.AUTO_MAX_DETECT_FRAMES))
        # Scene-text OCR: of the frames available in each window, read the SHARPEST.
        window_ms = int(settings.AUTO_SCENE_OCR_INTERVAL_S * 1000)
        if result.duration_ms and result.duration_ms / window_ms > settings.AUTO_SCENE_OCR_MAX:
            window_ms = int(np.ceil(result.duration_ms / settings.AUTO_SCENE_OCR_MAX))
        cur_win: dict = {"id": None, "best": []}      # best: [(sharp, frame, ts, idx)], top-N per window

        def flush_window() -> None:
            """OCR the sharpest frame of the window that just ended, then drop it (bounded memory)."""
            for _sharp, fr, ts, fidx in cur_win["best"]:
                texts = A._run_ocr(fr, (0, 0), 1.0, from_vehicle=False)
                for t in texts:
                    scene_texts.append(A.TextSighting(t.text, t.conf, ts, fidx,
                                                      A._rel(t.bbox_px, w, h), False))
                for norm, conf, bbox in _plate_reads_from_texts(texts):
                    plate_pool.append({"text": norm, "conf": conf, "ts_ms": ts,
                                       "bbox": A._rel(bbox, w, h), "track": None})
            cur_win["best"] = []

        tracks: Dict[str, _Track] = {}
        scene_texts: List[A.TextSighting] = []          # non-plate text for generic clues
        plate_pool: List[dict] = []                     # every plate read with provenance
        prev_gray: Optional[np.ndarray] = None
        idx, n_det = 0, 0

        def register(key: str, source: str, cls: str, conf: float, box: List[int],
                     frame: np.ndarray, ts_ms: int) -> None:
            t = tracks.get(key)
            if t is None:
                t = tracks[key] = _Track(key=key, source=source, first_ms=ts_ms)
            t.last_ms = ts_ms
            t.frames += 1
            t.cls_votes[cls] += conf
            crop = _padded_crop(frame, box)
            if crop.size:
                area_w = ((box[2] - box[0]) * (box[3] - box[1])) / frame_area
                t.color_votes[A.dominant_color_name(crop)] += max(area_w, 1e-3)
                q = _quality(crop, conf, frame_area)
                t.crops.append((q, crop, idx))
                t.crops.sort(key=lambda c: -c[0])
                del t.crops[settings.AUTO_CROPS_PER_TRACK:]
            if conf >= t.max_conf:
                t.max_conf, t.best_frame = conf, idx
                t.best_bbox_rel = A._rel(box, w, h)

        while True:
            if not cap.grab():
                break
            do_det = idx % det_stride == 0
            if not do_det:
                idx += 1
                continue
            ok, frame = cap.retrieve()
            if not ok or frame is None:
                idx += 1
                continue
            ts_ms = int(round(idx / fps * 1000))
            result.frames_analyzed += 1

            if do_det and (detector is not None or world is not None):
                # Cheap static-scene gate: skip near-identical frames when nothing was found.
                small = cv2.cvtColor(cv2.resize(frame, (96, 54)), cv2.COLOR_BGR2GRAY)
                static = prev_gray is not None and float(np.mean(cv2.absdiff(small, prev_gray))) < 0.6
                prev_gray = small
                if not (static and n_det > 0 and not any(
                        t.last_ms >= ts_ms - 2000 / settings.AUTO_DETECT_FPS for t in tracks.values())):
                    n_det += 1
                    coco_boxes: List[List[int]] = []
                    if detector is not None:
                        try:
                            r = detector.track(frame, persist=True, tracker="bytetrack.yaml",
                                               conf=A.MIN_OBJECT_CONF, imgsz=settings.AUTO_IMGSZ,
                                               verbose=False)[0]
                            ids = r.boxes.id.tolist() if r.boxes.id is not None else [None] * len(r.boxes)
                            for i, box in enumerate(r.boxes):
                                cls = r.names[int(box.cls[0])]
                                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                                b = [max(0, x1), max(0, y1), min(w, x2), min(h, y2)]
                                if b[2] <= b[0] or b[3] <= b[1]:
                                    continue
                                coco_boxes.append(b)
                                key = f"c{int(ids[i])}" if ids[i] is not None else f"c-f{idx}-{i}"
                                register(key, "coco", cls, float(box.conf[0]), b, frame, ts_ms)
                        except Exception as exc:
                            logger.warning("tracking failed: %s", exc)
                    if world is not None:
                        try:
                            r = world.track(frame, persist=True, tracker="bytetrack.yaml",
                                            conf=settings.OPEN_VOCAB_CONF, imgsz=settings.AUTO_IMGSZ,
                                            verbose=False)[0]
                            ids = r.boxes.id.tolist() if r.boxes.id is not None else [None] * len(r.boxes)
                            for i, box in enumerate(r.boxes):
                                cls = r.names[int(box.cls[0])]
                                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                                b = [max(0, x1), max(0, y1), min(w, x2), min(h, y2)]
                                if b[2] <= b[0] or b[3] <= b[1]:
                                    continue
                                # Prefer the COCO detector where both see the same thing.
                                if cls != PLATE_CLASS and any(_iou(b, c) > 0.5 for c in coco_boxes):
                                    continue
                                key = f"w{int(ids[i])}" if ids[i] is not None else f"w-f{idx}-{i}"
                                register(key, "openvocab", cls, float(box.conf[0]), b, frame, ts_ms)
                        except Exception as exc:
                            logger.warning("open-vocab tracking failed: %s", exc)
                if progress and total:
                    progress(min(idx + 1, total), total)

            if A._get_ocr() is not None:
                g = cv2.cvtColor(cv2.resize(frame, (320, max(1, int(320 * h / max(w, 1))))), cv2.COLOR_BGR2GRAY)
                # Denoise first: raw Laplacian variance rewards sensor noise, not focus.
                sharp = float(cv2.Laplacian(cv2.GaussianBlur(g, (5, 5), 0), cv2.CV_64F).var())
                win = ts_ms // window_ms
                if cur_win["id"] is not None and win != cur_win["id"]:
                    flush_window()
                cur_win["id"] = win
                best = cur_win["best"]
                if len(best) < settings.AUTO_SCENE_FRAMES_PER_WINDOW or sharp > best[-1][0]:
                    best.append((sharp, frame.copy(), ts_ms, idx))
                    best.sort(key=lambda b: -b[0])
                    del best[settings.AUTO_SCENE_FRAMES_PER_WINDOW:]
            idx += 1
    finally:
        cap.release()

    if A._get_ocr() is not None:
        flush_window()

    # ── finalise tracks ──────────────────────────────────────────────────────
    min_frames = settings.AUTO_MIN_TRACK_FRAMES if n_det >= 4 else 1
    kept = {k: t for k, t in tracks.items() if t.frames >= min_frames}

    # ── OCR the best crops of vehicles and plate boxes ──────────────────────
    budget = settings.AUTO_MAX_PLATE_OCR
    if A._get_ocr() is not None:
        for t in sorted(kept.values(), key=lambda t: -t.max_conf):
            is_plate_box = t.cls == PLATE_CLASS
            if not (t.cls in A.VEHICLE_CLASSES or is_plate_box):
                continue
            for _q, crop, frame_idx in t.crops:
                if budget <= 0:
                    break
                ch = crop.shape[0]
                variants = []
                if is_plate_box:
                    variants.append(_upscale(crop, 360))
                else:
                    variants.append(_upscale(crop[int(ch * 0.45):, :], 420))   # plate band
                    variants.append(_upscale(crop, 640))                       # whole vehicle
                for v in variants:
                    if budget <= 0:
                        break
                    budget -= 1
                    texts = A._run_ocr(v, (0, 0), 1.0, from_vehicle=True)
                    for norm, conf, _bb in _plate_reads_from_texts(texts):
                        plate_pool.append({"text": norm, "conf": conf, "ts_ms": t.first_ms,
                                           "bbox": t.best_bbox_rel, "track": t.key})

    # ── cluster + vote plates across the whole clip ─────────────────────────
    reads = [(p["text"], p["conf"]) for p in plate_pool]
    voted = [(cluster, vote(cluster)) for cluster in cluster_reads(reads)]
    voted = [(c, v) for c, v in voted if v is not None]
    strong_texts = [v.text for _c, v in voted if v.pattern != "RAW"]
    from rapidfuzz import fuzz as _fuzz
    for cluster, v in voted:
        if v.pattern == "RAW":
            # A fragment of a properly-formatted plate, or a one-off partial read,
            # is noise rather than a second plate.
            if any(_fuzz.partial_ratio(v.text, s) >= 85 for s in strong_texts):
                continue
            if v.n_reads < 2:
                continue
        members = [p for p in plate_pool
                   if any(p["text"] == t and abs(p["conf"] - c) < 1e-9 for t, c in cluster)]
        with_track = [m for m in members if m["track"]]
        anchor = min(with_track or members, key=lambda m: m["ts_ms"])
        keys = sorted({m["track"] for m in members if m["track"]})
        result.plates.append(A.PlateFinding(
            text=v.text, confidence=v.confidence, n_reads=v.n_reads, agreement=v.agreement,
            edits=v.edits, state_valid=v.state_valid, first_ms=anchor["ts_ms"],
            bbox_rel=anchor["bbox"], reads=v.reads, track_keys=keys))

    plate_by_track = {k: p.text for p in result.plates for k in p.track_keys}
    for t in kept.values():
        result.tracks.append(A.TrackSummary(
            key=t.key, cls=t.cls, color=t.color, source=t.source, first_ms=t.first_ms,
            last_ms=t.last_ms, frames=t.frames, max_conf=t.max_conf, best_frame=t.best_frame,
            best_bbox_rel=t.best_bbox_rel, plate=plate_by_track.get(t.key)))

    # Non-plate scene text goes through the generic clue extractor downstream.
    result.texts = scene_texts
    if progress:
        progress(1, 1)
    return result
