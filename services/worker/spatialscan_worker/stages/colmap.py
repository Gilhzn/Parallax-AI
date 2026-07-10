"""Stage 2 — recover camera poses.

Real mode shells out to nerfstudio's ``ns-process-data images`` (which drives
COLMAP feature extraction, matching, and sparse mapping and writes the
``transforms.json`` layout that ``ns-train`` consumes). Mock mode writes a
synthetic circular camera path in the same shape.
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

from ..capabilities import has_colmap, resolve_stage_mode


def estimate_poses(frames_dir: Path, out_dir: Path, pipeline_mode: str) -> Path:
    """Return the processed-data directory containing ``transforms.json``."""
    mode = resolve_stage_mode(pipeline_mode, has_colmap(), "poses")
    out_dir.mkdir(parents=True, exist_ok=True)
    if mode == "real":
        _estimate_real(frames_dir, out_dir)
    else:
        _estimate_mock(frames_dir, out_dir)
    transforms = out_dir / "transforms.json"
    if not transforms.exists():
        raise RuntimeError(f"pose estimation produced no transforms.json in {out_dir}")
    return out_dir


def _estimate_real(frames_dir: Path, out_dir: Path) -> None:
    cmd = [
        "ns-process-data",
        "images",
        "--data",
        str(frames_dir),
        "--output-dir",
        str(out_dir),
        "--sfm-tool",
        "colmap",
        # Video frames are temporally ordered: sequential matching is both
        # faster and more reliable than exhaustive for this footage.
        "--matching-method",
        "sequential",
        # Keep original resolution as the primary copy (downscales are still
        # generated for previews, but training can request scale factor 1).
        "--num-downscales",
        "2",
    ]
    subprocess.run(cmd, check=True)


def _estimate_mock(frames_dir: Path, out_dir: Path) -> None:
    frames = sorted(frames_dir.glob("frame_*.jpg"))
    n = max(len(frames), 1)
    radius = 1.5
    poses = []
    for i, frame in enumerate(frames):
        angle = 2 * math.pi * i / n
        # Camera on a circle at eye height, looking at the room center.
        poses.append(
            {
                "file_path": f"images/{frame.name}",
                "transform_matrix": [
                    [math.cos(angle), 0.0, -math.sin(angle), radius * math.sin(angle)],
                    [0.0, 1.0, 0.0, 1.5],
                    [math.sin(angle), 0.0, math.cos(angle), radius * math.cos(angle)],
                    [0.0, 0.0, 0.0, 1.0],
                ],
            }
        )
    transforms = {
        "camera_model": "OPENCV",
        "fl_x": 800.0,
        "fl_y": 800.0,
        "cx": 640.0,
        "cy": 360.0,
        "w": 1280,
        "h": 720,
        "frames": poses,
    }
    (out_dir / "transforms.json").write_text(json.dumps(transforms, indent=2))
