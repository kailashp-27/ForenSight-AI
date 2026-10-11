"""
backend/modules/vision/cv_engine.py
───────────────────────────────────
OpenCV engine for the "Operator" mechanics: exact-frame extraction and
region-of-interest (ROI) preparation for the local VLM.

Pipeline for one ROI:
  1. Open the video and read the exact frame (by index or timestamp).
  2. Crop the ROI with 10% context padding on each side.
  3. CLAHE contrast enhancement on the luminance channel.
  4. Mild unsharp mask to recover text/edge detail.
  5. Letterbox to a fixed 448x448 patch (aspect ratio preserved) so the VLM
     always receives a bounded, predictable token count.
  6. Encode the patch as Base64 PNG for the VLM payload.
  7. SHA-256 of the raw frame and of the final patch (chain-of-custody).

This module is deliberately pure: no database, no network, no FastAPI.
All functions are blocking — callers run them in a threadpool.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np

PATCH_SIZE = 448                 # final square patch edge, px
ROI_CONTEXT_PADDING = 0.10       # 10% border around the drawn box
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID = (8, 8)
UNSHARP_SIGMA = 1.2
UNSHARP_AMOUNT = 0.6             # "mild": 0.6 of the high-frequency residual


class VideoError(RuntimeError):
    """Raised when a video cannot be opened, probed or read."""


@dataclass(frozen=True)
class VideoProbe:
    fps: float
    frame_count: int
    width: int
    height: int

    @property
    def duration_ms(self) -> int:
        return int(self.frame_count / self.fps * 1000) if self.fps > 0 else 0


@dataclass(frozen=True)
class FrameInfo:
    index: int
    timestamp_ms: int
    timestamp_str: str          # HH:MM:SS:MS


@dataclass(frozen=True)
class PatchResult:
    patch_bgr: np.ndarray       # 448x448x3 uint8
    patch_b64: str              # PNG, Base64
    roi_px: List[int]           # requested box in source-frame pixels [x1,y1,x2,y2]
    crop_box_px: List[int]      # padded + clamped box actually cropped
    frame_sha256: str
    crop_sha256: str


# ── helpers ──────────────────────────────────────────────────────────────────

def format_timestamp(timestamp_ms: int) -> str:
    """Milliseconds → 'HH:MM:SS:MS' (the notation used across the workbench)."""
    timestamp_ms = max(0, int(timestamp_ms))
    hours, rem = divmod(timestamp_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, ms = divmod(rem, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{ms:03d}"


def sha256_file(path: Union[str, Path], chunk_size: int = 1 << 20) -> str:
    """Streaming SHA-256 of a file (constant memory for multi-GB CCTV exports)."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open(path: Union[str, Path]) -> cv2.VideoCapture:
    path = Path(path)
    if not path.is_file():
        raise VideoError(f"Video file not found: {path}")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise VideoError(f"OpenCV could not open video: {path.name}")
    return cap


# ── probing & frame extraction ───────────────────────────────────────────────

def probe_video(path: Union[str, Path]) -> VideoProbe:
    cap = _open(path)
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        cap.release()
    if frame_count <= 0 or width <= 0 or height <= 0:
        raise VideoError("Video reports no decodable frames")
    return VideoProbe(fps=fps, frame_count=frame_count, width=width, height=height)


def extract_frame(
    path: Union[str, Path],
    *,
    frame_index: Optional[int] = None,
    timestamp_ms: Optional[int] = None,
) -> Tuple[np.ndarray, FrameInfo, VideoProbe]:
    """
    Read one exact frame.

    The index is CLAMPED to the last valid frame rather than rejected: a
    scrubber dragged to its own maximum lands exactly on frame_count (one past
    the last index), which is a routine, valid request.
    """
    if (frame_index is None) == (timestamp_ms is None):
        raise ValueError("Provide exactly one of frame_index or timestamp_ms")

    cap = _open(path)
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if frame_count <= 0:
            raise VideoError("Video reports no decodable frames")

        if frame_index is None:
            frame_index = int(round(timestamp_ms / 1000.0 * fps)) if fps > 0 else 0
        frame_index = max(0, min(int(frame_index), frame_count - 1))

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok or frame is None:
            raise VideoError(f"Failed to decode frame {frame_index}")
    finally:
        cap.release()

    ts_ms = int(round(frame_index / fps * 1000)) if fps > 0 else 0
    info = FrameInfo(index=frame_index, timestamp_ms=ts_ms, timestamp_str=format_timestamp(ts_ms))
    probe = VideoProbe(fps=fps, frame_count=frame_count, width=width or frame.shape[1],
                       height=height or frame.shape[0])
    return frame, info, probe


# ── ROI preparation ──────────────────────────────────────────────────────────

def relative_to_pixels(
    x1: float, y1: float, x2: float, y2: float, width: int, height: int
) -> List[int]:
    """Relative 0-1 box → ordered, clamped pixel box [x1, y1, x2, y2]."""
    px1 = int(round(min(x1, x2) * width))
    py1 = int(round(min(y1, y2) * height))
    px2 = int(round(max(x1, x2) * width))
    py2 = int(round(max(y1, y2) * height))
    px1, px2 = max(0, min(px1, width)), max(0, min(px2, width))
    py1, py2 = max(0, min(py1, height)), max(0, min(py2, height))
    return [px1, py1, px2, py2]


def _apply_clahe(bgr: np.ndarray) -> np.ndarray:
    """CLAHE on the L channel only, so colour is not distorted."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_chan, a_chan, b_chan = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_GRID)
    merged = cv2.merge((clahe.apply(l_chan), a_chan, b_chan))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def _unsharp_mask(bgr: np.ndarray) -> np.ndarray:
    """Mild unsharp mask: original + amount * (original - gaussian blur)."""
    blurred = cv2.GaussianBlur(bgr, (0, 0), UNSHARP_SIGMA)
    return cv2.addWeighted(bgr, 1.0 + UNSHARP_AMOUNT, blurred, -UNSHARP_AMOUNT, 0)


def _letterbox(image: np.ndarray, size: int) -> np.ndarray:
    """Scale to fit inside size×size preserving aspect ratio; pad with black."""
    h, w = image.shape[:2]
    scale = size / float(max(h, w))
    new_w, new_h = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    resized = cv2.resize(image, (new_w, new_h), interpolation=interp)

    canvas = np.zeros((size, size, 3), dtype=np.uint8)
    top, left = (size - new_h) // 2, (size - new_w) // 2
    canvas[top:top + new_h, left:left + new_w] = resized
    return canvas


def prepare_roi_patch(frame: np.ndarray, roi_px: List[int]) -> PatchResult:
    """Crop (+10% padding), enhance and letterbox an ROI into a VLM-ready patch."""
    if frame is None or frame.ndim != 3:
        raise ValueError("frame must be a BGR image array")

    h, w = frame.shape[:2]
    x1, y1, x2, y2 = (int(v) for v in roi_px)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("ROI has zero area")

    pad_x = int(round((x2 - x1) * ROI_CONTEXT_PADDING))
    pad_y = int(round((y2 - y1) * ROI_CONTEXT_PADDING))
    cx1, cy1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
    cx2, cy2 = min(w, x2 + pad_x), min(h, y2 + pad_y)
    if cx2 <= cx1 or cy2 <= cy1:
        raise ValueError("ROI lies outside the frame")

    crop = frame[cy1:cy2, cx1:cx2]
    crop = _unsharp_mask(_apply_clahe(crop))
    patch = _letterbox(crop, PATCH_SIZE)

    ok, buf = cv2.imencode(".png", patch)
    if not ok:
        raise VideoError("Failed to encode ROI patch")

    return PatchResult(
        patch_bgr=patch,
        patch_b64=base64.b64encode(buf.tobytes()).decode("ascii"),
        roi_px=[x1, y1, x2, y2],
        crop_box_px=[cx1, cy1, cx2, cy2],
        frame_sha256=hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest(),
        crop_sha256=hashlib.sha256(patch.tobytes()).hexdigest(),
    )
