"""
backend/modules/auto_analysis.py
────────────────────────────────
Automatic, whole-file analysis of evidence (no operator interaction):

  VIDEO     sample frames across the whole clip → YOLOv8 object detection
            (+ colour) → EasyOCR on vehicle crops and full frames → merge
            per-frame hits into time segments.
  IMAGE     YOLOv8 + EasyOCR + EXIF (GPS, capture time).
  DOCUMENT  PDF text extraction per page.

Everything here is blocking / CPU-heavy and is called from a threadpool.
Models load lazily on first use and the module degrades gracefully: if a
library or its weights are unavailable, `capabilities()` reports it and the
file is marked as partially analysed rather than failing the case.

Honesty notes (surfaced in reports):
  • YOLOv8 and EasyOCR are used as PRE-TRAINED, unmodified checkpoints
    (COCO-80 classes); they have not been fine-tuned on forensic data.
  • Output is observational and unverified until a human approves it.
"""

from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend.config import settings

logger = logging.getLogger(__name__)

VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle"}
PERSON_CLASSES = {"person"}
MIN_OBJECT_CONF = 0.35
MIN_OCR_CONF = 0.30

_lock = threading.Lock()
_detector = None
_ocr = None
_load_errors: Dict[str, str] = {}


# ── model loading ────────────────────────────────────────────────────────────

def _get_detector():
    global _detector
    if _detector is None:
        with _lock:
            if _detector is None:
                try:
                    from ultralytics import YOLO
                    Path(settings.YOLO_MODEL).parent.mkdir(parents=True, exist_ok=True)
                    _detector = YOLO(settings.YOLO_MODEL)
                except Exception as exc:  # missing lib / weights / offline
                    _load_errors["detector"] = str(exc)
                    logger.warning("YOLO unavailable: %s", exc)
                    return None
    return _detector


_rapid = None


def _get_rapid():
    """Second, independent OCR engine (RapidOCR / ONNX) for ensemble voting."""
    global _rapid
    if not settings.OCR_ENSEMBLE:
        return None
    if _rapid is None:
        with _lock:
            if _rapid is None:
                try:
                    from rapidocr_onnxruntime import RapidOCR
                    _rapid = RapidOCR()
                except Exception as exc:
                    _load_errors["ocr_ensemble"] = str(exc)
                    logger.warning("RapidOCR unavailable: %s", exc)
                    _rapid = False
    return _rapid or None


def _get_ocr():
    global _ocr
    if _ocr is None:
        with _lock:
            if _ocr is None:
                try:
                    import easyocr
                    import torch
                    _ocr = easyocr.Reader(["en"], gpu=bool(torch.cuda.is_available() and settings.USE_GPU),
                                          verbose=False)
                except Exception as exc:
                    _load_errors["ocr"] = str(exc)
                    logger.warning("EasyOCR unavailable: %s", exc)
                    return None
    return _ocr


_world = None


def _get_world():
    """YOLO-World open-vocabulary detector (custom class names, no training)."""
    global _world
    if not settings.OPEN_VOCAB_ENABLED:
        return None
    if _world is None:
        with _lock:
            if _world is None:
                try:
                    from ultralytics import YOLOWorld
                    Path(settings.OPEN_VOCAB_MODEL).parent.mkdir(parents=True, exist_ok=True)
                    w = YOLOWorld(settings.OPEN_VOCAB_MODEL)
                    w.set_classes([c.strip() for c in settings.OPEN_VOCAB_CLASSES.split(",") if c.strip()])
                    _world = w
                except Exception as exc:
                    _load_errors["open_vocab"] = str(exc)
                    logger.warning("Open-vocabulary detector unavailable: %s", exc)
                    _world = False
    return _world or None


def capabilities() -> Dict[str, Any]:
    """Report which analysers can run (loads them if needed)."""
    return {
        "detector": _get_detector() is not None,
        "ocr": _get_ocr() is not None,
        "open_vocab": _get_world() is not None,
        "ocr_ensemble": _get_rapid() is not None,
        "gpu": bool(__import__("torch").cuda.is_available() and settings.USE_GPU),
        "open_vocab_classes": [c.strip() for c in settings.OPEN_VOCAB_CLASSES.split(",") if c.strip()],
        "detector_model": settings.YOLO_MODEL,
        "errors": dict(_load_errors),
        "note": "Pre-trained YOLOv8 (COCO) and EasyOCR checkpoints; not fine-tuned on forensic data.",
    }


# ── colour naming ────────────────────────────────────────────────────────────

def dominant_color_name(bgr: np.ndarray) -> str:
    """Coarse colour word for an object crop (centre region, HSV rules)."""
    if bgr is None or bgr.size == 0:
        return "unknown"
    h, w = bgr.shape[:2]
    core = bgr[h // 4: max(h // 4 + 1, 3 * h // 4), w // 4: max(w // 4 + 1, 3 * w // 4)]
    hsv = cv2.cvtColor(core, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    s_med = float(np.median(hsv[:, 1]))
    v_med = float(np.median(hsv[:, 2]))
    if v_med < 55:
        return "black"
    if s_med < 40:
        return "white" if v_med > 170 else "gray"
    hue = float(np.median(hsv[:, 0])) * 2  # OpenCV hue is 0-179
    for limit, name in ((15, "red"), (40, "orange"), (70, "yellow"), (160, "green"),
                        (255, "blue"), (290, "purple"), (345, "pink"), (361, "red")):
        if hue < limit:
            return name
    return "unknown"


# ── per-frame analysis ───────────────────────────────────────────────────────

@dataclass
class FrameObject:
    cls: str
    conf: float
    bbox_px: List[int]
    color: str


@dataclass
class FrameText:
    text: str
    conf: float
    bbox_px: List[int]
    from_vehicle: bool
    engine: str = "easyocr"


def _enhance_for_ocr(bgr: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def _run_ocr(img: np.ndarray, offset: Tuple[int, int] = (0, 0), scale: float = 1.0,
         from_vehicle: bool = False) -> List[FrameText]:
    reader = _get_ocr()
    if reader is None or img is None or img.size == 0:
        return []
    out: List[FrameText] = []
    try:
        results = reader.readtext(_enhance_for_ocr(img))
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return []
    def add(box, text, conf, engine):
        text = (text or "").strip()
        if not text or conf < MIN_OCR_CONF:
            return
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        out.append(FrameText(
            text=text, conf=float(conf), from_vehicle=from_vehicle, engine=engine,
            bbox_px=[int(min(xs) / scale + offset[0]), int(min(ys) / scale + offset[1]),
                     int(max(xs) / scale + offset[0]), int(max(ys) / scale + offset[1])],
        ))

    for box, text, conf in results:
        add(box, text, conf, "easyocr")

    rapid = _get_rapid()
    if rapid is not None:
        try:
            res, _ = rapid(_enhance_for_ocr(img))
            for box, text, conf in (res or []):
                add(box, text, float(conf), "rapidocr")
        except Exception as exc:
            logger.warning("RapidOCR failed: %s", exc)
    return out


def analyze_frame(frame: np.ndarray) -> Tuple[List[FrameObject], List[FrameText]]:
    """Detect objects, then OCR vehicle crops (upscaled) and the full frame."""
    objects: List[FrameObject] = []
    texts: List[FrameText] = []
    h, w = frame.shape[:2]

    detector = _get_detector()
    if detector is not None:
        try:
            res = detector.predict(frame, conf=MIN_OBJECT_CONF, verbose=False)[0]
            names = res.names
            for box in res.boxes:
                cls = names[int(box.cls[0])]
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                if x2 <= x1 or y2 <= y1:
                    continue
                objects.append(FrameObject(cls, float(box.conf[0]), [x1, y1, x2, y2],
                                           dominant_color_name(frame[y1:y2, x1:x2])))
        except Exception as exc:
            logger.warning("Detection failed: %s", exc)

    # Vehicle crops are where plates live — upscale them for OCR.
    for o in objects:
        if o.cls in VEHICLE_CLASSES:
            x1, y1, x2, y2 = o.bbox_px
            crop = frame[y1:y2, x1:x2]
            scale = 2.0 if max(crop.shape[:2]) < 500 else 1.0
            if scale != 1.0:
                crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            texts.extend(_run_ocr(crop, (x1, y1), scale, from_vehicle=True))

    texts.extend(_run_ocr(frame, (0, 0), 1.0, from_vehicle=False))
    return objects, texts


# ── result containers ────────────────────────────────────────────────────────

@dataclass
class ObjectSegment:
    cls: str
    color: str
    first_ms: int
    last_ms: int
    max_conf: float
    count: int
    best_frame: int
    best_bbox_rel: List[float]


@dataclass
class TextSighting:
    text: str
    conf: float
    ts_ms: int
    frame: int
    bbox_rel: List[float]
    from_vehicle: bool


@dataclass
class TrackSummary:
    """One physical object followed across frames (a tracked instance)."""
    key: str
    cls: str
    color: str
    source: str                 # "coco" | "openvocab"
    first_ms: int
    last_ms: int
    frames: int
    max_conf: float
    best_frame: int
    best_bbox_rel: List[float]
    plate: Optional[str] = None


@dataclass
class PlateFinding:
    """A number plate consolidated from many reads (voted + format-corrected)."""
    text: str
    confidence: float
    n_reads: int
    agreement: float
    edits: int
    state_valid: Optional[bool]
    first_ms: int
    bbox_rel: Optional[List[float]]
    reads: List[Tuple[str, float]] = field(default_factory=list)
    track_keys: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    kind: str                                   # VIDEO | IMAGE | DOCUMENT
    segments: List[ObjectSegment] = field(default_factory=list)
    texts: List[TextSighting] = field(default_factory=list)
    pages: List[Tuple[int, str]] = field(default_factory=list)   # (page_no, text)
    exif: Dict[str, Any] = field(default_factory=dict)
    frames_analyzed: int = 0
    duration_ms: int = 0
    warnings: List[str] = field(default_factory=list)
    tracks: List[TrackSummary] = field(default_factory=list)
    ocr_pages: set = field(default_factory=set)
    plates: List[PlateFinding] = field(default_factory=list)
    method: str = "legacy"


def _rel(bbox: List[int], w: int, h: int) -> List[float]:
    return [round(bbox[0] / w, 4), round(bbox[1] / h, 4), round(bbox[2] / w, 4), round(bbox[3] / h, 4)]


# ── video ────────────────────────────────────────────────────────────────────

def analyze_video_legacy(path: str | Path,
                         progress: Optional[Callable[[int, int], None]] = None) -> AnalysisResult:
    """Original fixed-interval sampler: per-frame detection + OCR, no tracking (benchmark baseline)."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError("OpenCV could not open the video")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 25.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration_s = total / fps if fps else 0.0
        interval_s = max(settings.AUTO_SAMPLE_INTERVAL_S, duration_s / max(1, settings.AUTO_MAX_FRAMES))
        step = max(1, int(round(interval_s * fps)))
        indices = list(range(0, max(total, 1), step))

        result = AnalysisResult(kind="VIDEO", duration_ms=int(duration_s * 1000))
        if _get_detector() is None:
            result.warnings.append("Object detector unavailable; objects not analysed.")
        if _get_ocr() is None:
            result.warnings.append("OCR unavailable; on-screen text not analysed.")

        open_segments: Dict[Tuple[str, str], ObjectSegment] = {}
        gap_ms = int(interval_s * 1000 * 2.5)

        for n, idx in enumerate(indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            ts_ms = int(round(idx / fps * 1000))
            objects, texts = analyze_frame(frame)
            result.frames_analyzed += 1

            seen_now = set()
            for o in objects:
                key = (o.cls, o.color)
                seen_now.add(key)
                seg = open_segments.get(key)
                if seg and ts_ms - seg.last_ms <= gap_ms:
                    seg.last_ms = ts_ms
                    seg.count += 1
                    if o.conf > seg.max_conf:
                        seg.max_conf, seg.best_frame = o.conf, idx
                        seg.best_bbox_rel = _rel(o.bbox_px, w, h)
                else:
                    if seg:
                        result.segments.append(seg)
                    open_segments[key] = ObjectSegment(
                        o.cls, o.color, ts_ms, ts_ms, o.conf, 1, idx, _rel(o.bbox_px, w, h))
            for t in texts:
                result.texts.append(TextSighting(t.text, t.conf, ts_ms, idx,
                                                 _rel(t.bbox_px, w, h), t.from_vehicle))
            if progress:
                progress(n + 1, len(indices))

        result.segments.extend(open_segments.values())
        return result
    finally:
        cap.release()


def analyze_video(path: str | Path,
                  progress: Optional[Callable[[int, int], None]] = None) -> AnalysisResult:
    """Default video analysis: detect -> track -> best crops -> plate voting."""
    from backend.modules import video_pipeline
    return video_pipeline.analyze_video(path, progress)


# ── image ────────────────────────────────────────────────────────────────────

def read_exif(path: str | Path) -> Dict[str, Any]:
    """GPS (decimal degrees) and capture time from EXIF, if present."""
    try:
        from PIL import Image, ExifTags
        with Image.open(path) as im:
            exif = im.getexif()
            if not exif:
                return {}
            out: Dict[str, Any] = {}
            dt = exif.get(36867) or exif.get(306)   # DateTimeOriginal / DateTime
            if not dt:
                try:
                    dt = exif.get_ifd(0x8769).get(36867)
                except Exception:
                    dt = None
            if dt:
                try:
                    out["captured_at"] = datetime.strptime(str(dt), "%Y:%m:%d %H:%M:%S").isoformat()
                except ValueError:
                    pass
            try:
                gps = exif.get_ifd(0x8825)
            except Exception:
                gps = {}
            if gps and 2 in gps and 4 in gps:
                def conv(v) -> float:
                    d, m, s = (float(x) for x in v)
                    return d + m / 60.0 + s / 3600.0
                lat = conv(gps[2]) * (-1 if gps.get(1) == "S" else 1)
                lon = conv(gps[4]) * (-1 if gps.get(3) == "W" else 1)
                if math.isfinite(lat) and math.isfinite(lon):
                    out["latitude"], out["longitude"] = round(lat, 6), round(lon, 6)
            return out
    except Exception as exc:
        logger.debug("EXIF read failed: %s", exc)
        return {}


def analyze_image(path: str | Path) -> AnalysisResult:
    frame = cv2.imread(str(path))
    if frame is None:
        raise RuntimeError("Could not decode image")
    h, w = frame.shape[:2]
    result = AnalysisResult(kind="IMAGE", frames_analyzed=1, exif=read_exif(path))
    if _get_detector() is None:
        result.warnings.append("Object detector unavailable; objects not analysed.")
    if _get_ocr() is None:
        result.warnings.append("OCR unavailable; text in the image not analysed.")

    objects, texts = analyze_frame(frame)
    for o in objects:
        result.segments.append(ObjectSegment(o.cls, o.color, 0, 0, o.conf, 1, 0, _rel(o.bbox_px, w, h)))
    for t in texts:
        result.texts.append(TextSighting(t.text, t.conf, 0, 0, _rel(t.bbox_px, w, h), t.from_vehicle))
    return result


# ── documents ────────────────────────────────────────────────────────────────

def analyze_pdf(path: str | Path) -> AnalysisResult:
    """
    Text per page. Pages with no usable text layer (scanned / photographed PDFs)
    are rendered and OCR'd instead, so image-only documents are not silently empty.
    """
    import fitz  # PyMuPDF
    result = AnalysisResult(kind="DOCUMENT")
    skipped_ocr = 0
    with fitz.open(str(path)) as doc:
        for i, page in enumerate(doc, start=1):
            if i > settings.PDF_MAX_PAGES:
                result.warnings.append(f"Only the first {settings.PDF_MAX_PAGES} pages were processed.")
                break
            text = (page.get_text("text") or "").strip()
            if len(text) < settings.PDF_OCR_MIN_CHARS:
                if _get_ocr() is None:
                    skipped_ocr += 1
                else:
                    ocr_text = _ocr_pdf_page(page, fitz)
                    if len(ocr_text) > len(text):
                        text = ocr_text
                        result.ocr_pages.add(i)
            if text.strip():
                result.pages.append((i, text))
        if skipped_ocr:
            result.warnings.append(f"{skipped_ocr} page(s) have no text layer and OCR is unavailable.")
        elif not result.pages:
            result.warnings.append("No text could be read from this PDF (blank or unreadable pages).")
    return result


def _ocr_pdf_page(page, fitz) -> str:
    """Render one PDF page and OCR it; returns reading-order text."""
    pix = page.get_pixmap(matrix=fitz.Matrix(settings.PDF_OCR_ZOOM, settings.PDF_OCR_ZOOM), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 1:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    else:
        img = cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2BGR)
    lines = _run_ocr(img, (0, 0), 1.0, from_vehicle=False)
    if not lines:
        return ""
    # Both engines read the same page: keep the one that produced more text.
    by_engine: Dict[str, List[FrameText]] = {}
    for ln in lines:
        by_engine.setdefault(ln.engine, []).append(ln)
    chosen = max(by_engine.values(), key=lambda g: sum(len(t.text) for t in g))
    heights = sorted(t.bbox_px[3] - t.bbox_px[1] for t in chosen)
    band = max(8, heights[len(heights) // 2] * 0.7)
    rows: Dict[int, List[FrameText]] = {}
    for t in chosen:
        rows.setdefault(int(t.bbox_px[1] // band), []).append(t)
    return "\n".join(" ".join(t.text for t in sorted(r, key=lambda t: t.bbox_px[0]))
                     for _k, r in sorted(rows.items()))


# Detector class names that read as conclusory are reported as shapes, never as
# "weapon": the project's objective-lexicon rule applies to model labels too.
_OBJECTIVE_CLASS = {
    "knife": "knife-shaped metallic object",
    "scissors": "scissor-shaped metallic object",
    "gun": "handgun-shaped object",
    "baseball bat": "bat-shaped object",
    "crowbar": "crowbar-shaped metallic object",
    "hammer": "hammer-shaped object",
}


def objective_class_label(cls: str) -> str:
    return _OBJECTIVE_CLASS.get(cls, cls)


def category_for(cls: str) -> str:
    if cls in PERSON_CLASSES:
        return "PERSON"
    if cls in VEHICLE_CLASSES:
        return "VEHICLE"
    return "OBJECT"
