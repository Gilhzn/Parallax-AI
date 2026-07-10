"""The single pipeline orchestrator.

Every entrypoint — the dev Redis queue worker, the RunPod serverless handler,
and the Colab/GCP CLI — funnels into :func:`run_pipeline`. Keeping one code
path is the load-bearing structural decision of the worker.

Quality is controlled by a named preset (see :mod:`.quality`) with optional
per-field overrides; ``high`` reconstructs at full input resolution with no
quality-reducing shortcuts.

For remote entrypoints, :func:`process_payload` wraps the pipeline with
presigned-URL download/upload so the worker never needs storage credentials.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .quality import QualityPreset, get_preset
from .stages import colmap, export, frames, train

# stage name -> share of overall progress
STAGE_WEIGHTS: list[tuple[str, float]] = [
    ("frames", 0.10),
    ("poses", 0.30),
    ("training", 0.50),
    ("export", 0.10),
]
STAGES = [name for name, _ in STAGE_WEIGHTS]

# reporter(stage, overall_progress 0..1)
Reporter = Callable[[str, float], None]


def _env_opt_float(name: str) -> float | None:
    raw = os.environ.get(name)
    return float(raw) if raw not in (None, "") else None


@dataclass
class JobSpec:
    job_id: str
    video_path: Path
    output_dir: Path
    metadata: dict | None = None
    pipeline_mode: str = field(default_factory=lambda: os.environ.get("PIPELINE_MODE", "auto"))
    quality: str = field(default_factory=lambda: os.environ.get("QUALITY_PRESET", "balanced"))
    # Optional overrides on top of the preset (None = use the preset's value)
    frames_per_second: float | None = field(default_factory=lambda: _env_opt_float("FRAMES_PER_SECOND"))
    train_iterations: int | None = field(
        default_factory=lambda: (
            int(v) if (v := _env_opt_float("TRAIN_ITERATIONS")) is not None else None
        )
    )
    splat_max_mb: float | None = field(default_factory=lambda: _env_opt_float("SPLAT_MAX_MB"))

    def resolved_preset(self) -> QualityPreset:
        preset = get_preset(self.quality)
        overrides = {}
        if self.frames_per_second is not None:
            overrides["fps"] = self.frames_per_second
        if self.train_iterations is not None:
            overrides["train_iterations"] = self.train_iterations
        if self.splat_max_mb is not None:
            overrides["splat_max_mb"] = self.splat_max_mb
        return dataclasses.replace(preset, **overrides) if overrides else preset


@dataclass
class PipelineResult:
    splat_path: Path
    manifest_path: Path
    manifest: dict
    ply_path: Path | None = None  # lossless archive, quality presets with keep_ply


def run_pipeline(spec: JobSpec, report: Reporter | None = None) -> PipelineResult:
    started = time.time()
    preset = spec.resolved_preset()
    work = spec.output_dir
    work.mkdir(parents=True, exist_ok=True)

    def emit(stage: str, stage_progress: float) -> None:
        if report is None:
            return
        overall = 0.0
        for name, weight in STAGE_WEIGHTS:
            if name == stage:
                overall += weight * min(max(stage_progress, 0.0), 1.0)
                break
            overall += weight
        report(stage, round(overall, 4))

    duration = None
    if spec.metadata:
        duration = spec.metadata.get("duration_sec") or spec.metadata.get("durationSec")

    emit("frames", 0.0)
    frame_paths = frames.extract_frames(
        spec.video_path,
        work / "frames",
        preset=preset,
        pipeline_mode=spec.pipeline_mode,
        video_duration_sec=duration,
    )
    emit("frames", 1.0)

    emit("poses", 0.0)
    processed_dir = colmap.estimate_poses(
        work / "frames", work / "processed", pipeline_mode=spec.pipeline_mode
    )
    emit("poses", 1.0)

    emit("training", 0.0)
    trained = train.train_gaussians(
        processed_dir,
        work,
        preset=preset,
        pipeline_mode=spec.pipeline_mode,
        on_progress=lambda p: emit("training", p),
    )
    emit("training", 1.0)

    emit("export", 0.0)
    splat_path = export.export_splat(trained.cloud, work / "scene.splat", max_mb=preset.splat_max_mb)

    ply_path = None
    if trained.ply_path is not None and trained.ply_path.exists():
        ply_path = work / "scene.ply"
        shutil.copyfile(trained.ply_path, ply_path)

    manifest = {
        "job_id": spec.job_id,
        "splat_file": splat_path.name,
        "splat_count": splat_path.stat().st_size // 32,
        "size_bytes": splat_path.stat().st_size,
        "frame_count": len(frame_paths),
        "pipeline_mode": spec.pipeline_mode,
        "quality": preset.name,
        "train_iterations": preset.train_iterations,
        "model": preset.model,
        "sh_degree": preset.sh_degree,
        "full_resolution": preset.full_resolution,
        "ply_file": ply_path.name if ply_path else None,
        "elapsed_sec": round(time.time() - started, 2),
        "metadata": spec.metadata or {},
    }
    manifest_path = work / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    emit("export", 1.0)

    return PipelineResult(
        splat_path=splat_path, manifest_path=manifest_path, manifest=manifest, ply_path=ply_path
    )


def process_payload(payload: dict, report: Reporter | None = None) -> dict:
    """Run a job described by presigned URLs (queue worker / RunPod handler).

    Expected payload::

        {
          "job_id": "...",
          "video_url": "<presigned GET>",
          "splat_put_url": "<presigned PUT>",
          "manifest_put_url": "<presigned PUT>",
          "ply_put_url": "<presigned PUT>",     # optional, quality=high
          "quality": "fast|balanced|high",       # optional
          "metadata": {...}                      # optional client metadata
        }
    """
    job_id = payload["job_id"]
    with tempfile.TemporaryDirectory(prefix=f"spatialscan-{job_id}-") as tmp:
        tmp_path = Path(tmp)
        video_path = tmp_path / "input.mp4"
        with httpx.Client(timeout=300) as client:
            resp = client.get(payload["video_url"])
            resp.raise_for_status()
            video_path.write_bytes(resp.content)

            spec_kwargs = {}
            if payload.get("quality"):
                spec_kwargs["quality"] = payload["quality"]
            spec = JobSpec(
                job_id=job_id,
                video_path=video_path,
                output_dir=tmp_path / "out",
                metadata=payload.get("metadata"),
                **spec_kwargs,
            )
            result = run_pipeline(spec, report=report)

            uploads = [
                ("splat_put_url", result.splat_path, "application/octet-stream"),
                ("manifest_put_url", result.manifest_path, "application/json"),
            ]
            if result.ply_path is not None and payload.get("ply_put_url"):
                uploads.append(("ply_put_url", result.ply_path, "application/octet-stream"))
            for url_key, path, content_type in uploads:
                put = client.put(
                    payload[url_key],
                    content=path.read_bytes(),
                    headers={"Content-Type": content_type},
                )
                put.raise_for_status()

    return result.manifest
