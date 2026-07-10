"""Stage 3 — train the 3D Gaussian Splatting model.

Real mode drives nerfstudio's gsplat-backed methods via subprocess:
``ns-train splatfacto|splatfacto-big`` followed by ``ns-export
gaussian-splat``, then loads the exported PLY. The quality preset decides
model capacity, iteration count, spherical-harmonics degree and whether the
input images may be downscaled. Mock mode returns the synthetic room while
emitting the same progress callbacks, so the rest of the system behaves
identically.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from ..capabilities import has_nerfstudio, resolve_stage_mode
from ..ply_io import ply_to_cloud
from ..quality import QualityPreset
from ..splat_format import SplatCloud
from ..synthetic import synthetic_room_splats

ProgressFn = Callable[[float], None]


class TrainResult:
    def __init__(self, cloud: SplatCloud, ply_path: Path | None = None):
        self.cloud = cloud
        self.ply_path = ply_path  # lossless archive (real mode, keep_ply presets)


def train_gaussians(
    processed_dir: Path,
    work_dir: Path,
    preset: QualityPreset,
    pipeline_mode: str,
    on_progress: ProgressFn | None = None,
) -> TrainResult:
    mode = resolve_stage_mode(pipeline_mode, has_nerfstudio(), "training")
    if mode == "real":
        return _train_real(processed_dir, work_dir, preset, on_progress)
    return _train_mock(preset, on_progress)


def _train_real(
    processed_dir: Path,
    work_dir: Path,
    preset: QualityPreset,
    on_progress: ProgressFn | None,
) -> TrainResult:
    out_root = work_dir / "training"
    out_root.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ns-train", preset.model,
        "--data", str(processed_dir),
        "--output-dir", str(out_root),
        "--max-num-iterations", str(preset.train_iterations),
        "--pipeline.model.sh-degree", str(preset.sh_degree),
        "--viewer.quit-on-train-completion", "True",
        "--vis", "viewer",
    ]
    if preset.full_resolution:
        # Forbid nerfstudio's automatic image downscaling — train on the
        # exact pixels the phone captured.
        cmd += ["nerfstudio-data", "--downscale-factor", "1"]
    subprocess.run(cmd, check=True)
    if on_progress:
        on_progress(0.9)

    configs = sorted(out_root.rglob("config.yml"), key=lambda p: p.stat().st_mtime)
    if not configs:
        raise RuntimeError(f"ns-train finished but no config.yml found under {out_root}")
    export_dir = work_dir / "export"
    subprocess.run(
        [
            "ns-export", "gaussian-splat",
            "--load-config", str(configs[-1]),
            "--output-dir", str(export_dir),
        ],
        check=True,
    )
    plys = sorted(export_dir.glob("*.ply"))
    if not plys:
        raise RuntimeError(f"ns-export produced no .ply in {export_dir}")
    cloud = ply_to_cloud(plys[-1])
    if on_progress:
        on_progress(1.0)
    return TrainResult(cloud, ply_path=plys[-1] if preset.keep_ply else None)


def _train_mock(preset: QualityPreset, on_progress: ProgressFn | None) -> TrainResult:
    # Simulate a handful of optimization checkpoints so progress UIs animate.
    steps = 5
    for i in range(1, steps + 1):
        time.sleep(0.05)
        if on_progress:
            on_progress(i / steps)
    return TrainResult(synthetic_room_splats(seed=preset.train_iterations % 2**31))
