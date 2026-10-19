"""
backend/training/cli.py
───────────────────────
Command-line entry points for the review -> fine-tune loop.

    # 1. export investigator-reviewed detections as a YOLO dataset
    python -m backend.training.cli export --out data/yolo_case --case <case_id>

    # 2. fine-tune the detector on it (CPU is fine for small sets; GPU is faster)
    python -m backend.training.cli train --data data/yolo_case/data.yaml --epochs 40

    # 3. use the result: set YOLO_MODEL=<printed path> in .env and restart.

Fine-tuning needs REVIEWED data. A handful of images will overfit; aim for
hundreds of confirmed boxes per class and hold out a validation split. The
printed metrics are on that split only — they are not a guarantee on new
footage. Keep the previous weights so you can roll back.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import time
from pathlib import Path

from backend.config import settings
from backend.training.dataset import export_dataset, fetch_reviewed


def _export(args: argparse.Namespace) -> None:
    from backend.database.db import init_db

    async def go():
        await init_db()
        return await fetch_reviewed(args.case)

    rows = asyncio.run(go())
    if not rows:
        raise SystemExit("No reviewed detections found. Confirm/reject detections in the "
                         "Investigation board's Review tab first.")
    summary = export_dataset(rows, args.out)
    print(json.dumps(summary, indent=2))
    if len(summary["classes"]) < 3 or summary["positives"] < 100:
        print("\nWARNING: this is a small / narrow dataset. Fine-tuning on only a few classes makes "
              "the detector forget the others (catastrophic forgetting). Review more detections of "
              "ALL classes you care about before training, and compare against the current weights "
              "with backend.tools.benchmark_video before switching.")


def _train(args: argparse.Namespace) -> None:
    from ultralytics import YOLO

    base = args.base or settings.YOLO_MODEL
    model = YOLO(base)
    results = model.train(
        data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        project=str(Path(args.project).resolve()), name=args.name, exist_ok=True,
        patience=max(10, args.epochs // 4), verbose=False,
    )
    best = Path(results.save_dir) / "weights" / "best.pt"
    if not best.exists():
        raise SystemExit("Training finished but best.pt was not produced")
    dest = Path(settings.YOLO_MODEL).parent / f"custom_{time.strftime('%Y%m%d_%H%M%S')}.pt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(best, dest)
    print(f"\nFine-tuned weights saved to: {dest}")
    print(f'To use them: set YOLO_MODEL="{dest.as_posix()}" in .env and restart the backend.')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("export", help="export reviewed detections as a YOLO dataset")
    e.add_argument("--out", required=True)
    e.add_argument("--case", help="limit to one case id")
    e.set_defaults(fn=_export)

    t = sub.add_parser("train", help="fine-tune YOLO on an exported dataset")
    t.add_argument("--data", required=True, help="path to data.yaml")
    t.add_argument("--base", help="starting weights (default: current YOLO_MODEL)")
    t.add_argument("--epochs", type=int, default=40)
    t.add_argument("--imgsz", type=int, default=640)
    t.add_argument("--batch", type=int, default=8)
    t.add_argument("--project", default="backend/storage/training_runs")
    t.add_argument("--name", default="custom")
    t.set_defaults(fn=_train)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
