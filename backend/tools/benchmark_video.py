"""
backend/tools/benchmark_video.py
────────────────────────────────
Measure video-analysis accuracy so improvements are evidence, not opinion.

Compares, on the SAME clips:
  legacy    fixed-interval sampling, per-frame OCR, take the best reading
  tracking  detect -> track -> best crops -> multi-read plate voting + format fixes

Two suites:
  plates    synthetic clips of a moving number plate with random blur / noise /
            down-scaling / JPEG artefacts. Metric: exact-match plate accuracy.
  counting  a still scene jittered into a clip. Metric: unique person count vs
            the count found on the clean image by the detector (pseudo ground
            truth — a real labelled set should replace it).

Usage (from the repo root):
    python -m backend.tools.benchmark_video --clips 12 --image path/to/people.jpg
    python -m backend.tools.benchmark_video --videos DIR --truth truth.json
        truth.json = {"clip1.mp4": {"plate": "TN09AB1234", "persons": 3}, ...}

This is a REGRESSION/COMPARISON tool, not proof of real-world accuracy:
synthetic degradations only approximate real CCTV.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

from backend.modules import auto_analysis as A
from backend.modules import video_pipeline
from backend.modules.clue_text import extract_clues

STATES = ["TN", "KA", "MH", "DL", "KL", "AP", "UP", "GJ"]
LETTERS = "ABCDEFGHJKLMNPRSTUVWXY"


def random_plate(rng: random.Random) -> str:
    return (f"{rng.choice(STATES)}{rng.randint(1, 99):02d}"
            f"{''.join(rng.choice(LETTERS) for _ in range(rng.choice([1, 2, 2])))}{rng.randint(1000, 9999)}")


def _plate_image(text: str) -> np.ndarray:
    spaced = f"{text[:2]} {text[2:4]} {text[4:-4]} {text[-4:]}"
    img = np.full((140, 440, 3), 238, np.uint8)
    cv2.rectangle(img, (5, 5), (434, 134), (0, 0, 0), 4)
    cv2.putText(img, spaced, (22, 92), cv2.FONT_HERSHEY_DUPLEX, 1.7, (12, 12, 12), 3, cv2.LINE_AA)
    return img


def make_plate_clip(path: Path, text: str, rng: random.Random, frames: int = 60, fps: int = 10,
                    hard: bool = False) -> None:
    """Moving plate on a noisy background, with per-clip random degradation."""
    if hard:   # roughly: distant, out-of-focus, heavily compressed plate
        blur, noise = rng.uniform(1.5, 3.6), rng.uniform(18, 42)
        scale, jpeg = rng.uniform(0.28, 0.5), rng.randint(12, 40)
    else:
        blur, noise = rng.uniform(0.0, 2.2), rng.uniform(4, 22)
        scale, jpeg = rng.uniform(0.45, 0.8), rng.randint(25, 70)
    base = _plate_image(text)
    base = cv2.resize(base, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ph, pw = base.shape[:2]

    raw = path.with_suffix(".avi")
    vw = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"MJPG"), fps, (640, 360))
    for i in range(frames):
        bg = np.full((360, 640, 3), (55, 48, 44), np.uint8)
        x = int(30 + (i * (640 - pw - 60)) / frames)
        y = 140 + int(12 * np.sin(i / 6))
        frame = bg.copy()
        frame[y:y + ph, x:x + pw] = base
        if blur > 0.2:
            frame = cv2.GaussianBlur(frame, (0, 0), blur)
        frame = np.clip(frame.astype(np.int16) + np.random.default_rng(rng.randint(0, 10**6))
                        .normal(0, noise, frame.shape), 0, 255).astype(np.uint8)
        ok, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg])
        vw.write(cv2.imdecode(enc, cv2.IMREAD_COLOR))
    vw.release()
    # Re-encode to a browser/OpenCV-friendly container when ffmpeg is present.
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "libvpx",
                        "-b:v", "1M", "-pix_fmt", "yuv420p", str(path)], check=True)
        raw.unlink(missing_ok=True)
    else:
        raw.replace(path)


def make_count_clip(path: Path, image: Path, frames: int = 45, fps: int = 15) -> None:
    img = cv2.imread(str(image))
    h, w = img.shape[:2]
    scale = 640 / w
    img = cv2.resize(img, (640, int(h * scale)))
    h, w = img.shape[:2]
    raw = path.with_suffix(".avi")
    vw = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"MJPG"), fps, (w, h))
    for i in range(frames):
        M = np.float32([[1, 0, 4 * np.sin(i / 4)], [0, 1, 3 * np.cos(i / 5)]])
        f = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)
        vw.write(f)
    vw.release()
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "libvpx",
                        "-b:v", "2M", "-pix_fmt", "yuv420p", str(path)], check=True)
        raw.unlink(missing_ok=True)
    else:
        raw.replace(path)


# ── method adapters ──────────────────────────────────────────────────────────

def _legacy_plate(path: Path) -> Optional[str]:
    res = A.analyze_video_legacy(path)
    best, conf = None, -1.0
    for t in res.texts:
        for c in extract_clues(t.text):
            if c.kind == "PLATE" and t.conf > conf:
                best, conf = c.norm, t.conf
    return best


def _tracking_plate(path: Path) -> Optional[str]:
    res = video_pipeline.analyze_video(path)
    if not res.plates:
        return None
    return max(res.plates, key=lambda p: p.confidence).text


def _norm(s: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _edit_distance(a: str, b: str) -> int:
    from rapidfuzz.distance import Levenshtein
    return Levenshtein.distance(a, b)


def run(plate_truth: Dict[Path, str], count_truth: Dict[Path, int]) -> dict:
    report: dict = {"plates": {}, "counting": {}}

    if plate_truth:
        for name, fn in (("legacy", _legacy_plate), ("tracking", _tracking_plate)):
            hits, dist, secs = 0, 0, 0.0
            rows = []
            for path, truth in plate_truth.items():
                t0 = time.time()
                got = fn(path)
                secs += time.time() - t0
                ok = _norm(got) == _norm(truth)
                hits += ok
                dist += _edit_distance(_norm(got), _norm(truth))
                rows.append({"clip": path.name, "truth": truth, "read": got, "ok": ok})
            n = len(plate_truth)
            report["plates"][name] = {
                "exact_match": f"{hits}/{n}", "accuracy": round(hits / n, 3),
                "mean_edit_distance": round(dist / n, 2), "seconds_per_clip": round(secs / n, 1),
                "rows": rows,
            }

    for path, truth in count_truth.items():
        legacy = A.analyze_video_legacy(path)
        trk = video_pipeline.analyze_video(path)
        report["counting"][path.name] = {
            "truth_persons": truth,
            "legacy_unique_persons": sum(1 for s in legacy.segments if s.cls == "person"),
            "tracking_unique_persons": sum(1 for t in trk.tracks if t.cls == "person"),
        }
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clips", type=int, default=10, help="number of synthetic plate clips")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--hard", action="store_true", help="heavier blur/noise/down-scaling")
    ap.add_argument("--image", type=Path, help="people photo for the counting suite")
    ap.add_argument("--videos", type=Path, help="directory of real clips (needs --truth)")
    ap.add_argument("--truth", type=Path, help="JSON ground truth for --videos")
    ap.add_argument("--json", type=Path, help="write the full report here")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    tmp = Path(tempfile.mkdtemp(prefix="fs_bench_"))
    plate_truth: Dict[Path, str] = {}
    count_truth: Dict[Path, int] = {}

    if args.videos and args.truth:
        truth = json.loads(args.truth.read_text())
        for name, t in truth.items():
            p = args.videos / name
            if "plate" in t:
                plate_truth[p] = t["plate"]
            if "persons" in t:
                count_truth[p] = int(t["persons"])
    else:
        for i in range(args.clips):
            text = random_plate(rng)
            p = tmp / f"plate_{i:02d}.webm"
            make_plate_clip(p, text, rng, hard=args.hard)
            plate_truth[p] = text
        if args.image:
            det = A._get_detector()
            n = sum(1 for b in det.predict(cv2.imread(str(args.image)), conf=0.5, verbose=False)[0].boxes
                    if det.names[int(b.cls[0])] == "person")
            p = tmp / "people.webm"
            make_count_clip(p, args.image)
            count_truth[p] = n

    report = run(plate_truth, count_truth)
    for suite, data in (("PLATES", report["plates"]),):
        for m, d in data.items():
            print(f"[{suite}] {m:9s} accuracy={d['accuracy']:.0%} ({d['exact_match']}) "
                  f"mean_edit_distance={d['mean_edit_distance']} {d['seconds_per_clip']}s/clip")
    for clip, d in report["counting"].items():
        print(f"[COUNT ] {clip}: truth={d['truth_persons']} legacy={d['legacy_unique_persons']} "
              f"tracking={d['tracking_unique_persons']}")
    if args.json:
        args.json.write_text(json.dumps(report, indent=2))
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
