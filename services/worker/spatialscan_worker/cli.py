"""Standalone CLI entrypoint — the Colab / GCP-VM / laptop path.

Example::

    python -m spatialscan_worker.cli --video my_room.mp4 --out ./out --mode auto

Produces ``out/scene.splat`` + ``out/manifest.json``. On a GPU machine with
ffmpeg, COLMAP and nerfstudio installed, ``--mode auto`` runs the real
pipeline end to end; anywhere else it degrades to the synthetic mock so the
plumbing can still be exercised.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from .pipeline import JobSpec, run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="spatialscan-worker", description=__doc__)
    parser.add_argument("--video", required=True, type=Path, help="input video file (mp4)")
    parser.add_argument("--out", required=True, type=Path, help="output directory")
    parser.add_argument("--mode", default="auto", choices=["mock", "auto", "real"])
    parser.add_argument("--fps", type=float, default=3.0, help="frame extraction rate")
    parser.add_argument("--iterations", type=int, default=5000, help="3DGS training iterations")
    parser.add_argument("--max-mb", type=float, default=40.0, help=".splat size budget (MB)")
    args = parser.parse_args(argv)

    if not args.video.exists():
        parser.error(f"video not found: {args.video}")

    def report(stage: str, progress: float) -> None:
        print(f"[{progress * 100:5.1f}%] {stage}", flush=True)

    spec = JobSpec(
        job_id=uuid.uuid4().hex[:12],
        video_path=args.video,
        output_dir=args.out,
        pipeline_mode=args.mode,
        frames_per_second=args.fps,
        train_iterations=args.iterations,
        splat_max_mb=args.max_mb,
    )
    result = run_pipeline(spec, report=report)
    print(json.dumps(result.manifest, indent=2))
    print(f"\nscene: {result.splat_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
