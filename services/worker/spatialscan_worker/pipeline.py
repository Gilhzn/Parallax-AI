"""The single pipeline orchestrator.

Every entrypoint — the dev Redis queue worker, the RunPod serverless handler,
and the Colab/GCP CLI — funnels into :func:`run_pipeline`. Keeping one code
path is the load-bearing structural decision of the worker.

For remote entrypoints, :func:`process_payload` wraps the pipeline with
presigned-URL download/upload so the worker never needs storage credentials.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx

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


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


@dataclass
class JobSpec:
    job_id: str
    video_path: Path
    output_dir: Path
    metadata: dict | None = None
    pipeline_mode: str = field(default_factory=lambda: os.environ.get("PIPELINE_MODE", "auto"))
    frames_per_second: float = field(default_factory=lambda: _env_float("FRAMES_PER_SECOND", 3))
    train_iterations: int = field(default_factory=lambda: int(_env_float("TRAIN_ITERATIONS", 5000)))
    splat_max_mb: float = field(default_factory=lambda: _env_float("SPLAT_MAX_MB", 40))


@dataclass
class PipelineResult:
    splat_path: Path
    manifest_path: Path
    manifest: dict


def run_pipeline(spec: JobSpec, report: Reporter | None = None) -> PipelineResult:
    started = time.time()
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
        fps=spec.frames_per_second,
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
    cloud = train.train_gaussians(
        processed_dir,
        work,
        iterations=spec.train_iterations,
        pipeline_mode=spec.pipeline_mode,
        on_progress=lambda p: emit("training", p),
    )
    emit("training", 1.0)

    emit("export", 0.0)
    splat_path = export.export_splat(cloud, work / "scene.splat", max_mb=spec.splat_max_mb)
    manifest = {
        "job_id": spec.job_id,
        "splat_file": splat_path.name,
        "splat_count": splat_path.stat().st_size // 32,
        "size_bytes": splat_path.stat().st_size,
        "frame_count": len(frame_paths),
        "pipeline_mode": spec.pipeline_mode,
        "train_iterations": spec.train_iterations,
        "elapsed_sec": round(time.time() - started, 2),
        "metadata": spec.metadata or {},
    }
    manifest_path = work / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    emit("export", 1.0)

    return PipelineResult(splat_path=splat_path, manifest_path=manifest_path, manifest=manifest)


def process_payload(payload: dict, report: Reporter | None = None) -> dict:
    """Run a job described by presigned URLs (queue worker / RunPod handler).

    Expected payload::

        {
          "job_id": "...",
          "video_url": "<presigned GET>",
          "splat_put_url": "<presigned PUT>",
          "manifest_put_url": "<presigned PUT>",
          "metadata": {...}                     # optional client metadata
        }
    """
    job_id = payload["job_id"]
    with tempfile.TemporaryDirectory(prefix=f"spatialscan-{job_id}-") as tmp:
        tmp_path = Path(tmp)
        video_path = tmp_path / "input.mp4"
        with httpx.Client(timeout=120) as client:
            resp = client.get(payload["video_url"])
            resp.raise_for_status()
            video_path.write_bytes(resp.content)

            spec = JobSpec(
                job_id=job_id,
                video_path=video_path,
                output_dir=tmp_path / "out",
                metadata=payload.get("metadata"),
            )
            result = run_pipeline(spec, report=report)

            for url_key, path, content_type in (
                ("splat_put_url", result.splat_path, "application/octet-stream"),
                ("manifest_put_url", result.manifest_path, "application/json"),
            ):
                put = client.put(
                    payload[url_key],
                    content=path.read_bytes(),
                    headers={"Content-Type": content_type},
                )
                put.raise_for_status()

    return result.manifest
