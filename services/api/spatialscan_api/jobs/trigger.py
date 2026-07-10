"""Worker trigger strategies.

All three build the same presigned-URL payload understood by
``spatialscan_worker.pipeline.process_payload``:

* ``InlineTrigger`` — runs the pipeline in a background thread inside the API
  process (mock mode, zero external services). The local demo path.
* ``RedisQueueTrigger`` — LPUSH onto ``spatialscan:jobs`` for the dev queue
  worker (docker-compose).
* ``RunPodTrigger`` — POST to a RunPod Serverless endpoint; GPUs wake per
  job and scale to zero. The production path.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Protocol

import httpx
import redis

from ..config import Settings
from ..storage.base import Storage
from .store import JobStore

log = logging.getLogger("spatialscan.api")

QUEUE_KEY = "spatialscan:jobs"


def build_payload(
    job_id: str, video_key: str, metadata: dict | None, storage: Storage, quality: str = "balanced"
) -> dict:
    payload = {
        "job_id": job_id,
        "video_url": storage.presign_get(f"jobs/{job_id}/input.mp4"),
        "splat_put_url": storage.presign_put(f"jobs/{job_id}/scene.splat"),
        "manifest_put_url": storage.presign_put(f"jobs/{job_id}/manifest.json"),
        "quality": quality,
        "metadata": metadata or {},
    }
    if quality == "high":
        # High quality keeps the lossless PLY (full spherical harmonics)
        # next to the web-ready .splat.
        payload["ply_put_url"] = storage.presign_put(f"jobs/{job_id}/scene.ply")
    return payload


class JobTrigger(Protocol):
    def dispatch(
        self, job_id: str, video_key: str, metadata: dict | None, quality: str = "balanced"
    ) -> None: ...


class InlineTrigger:
    """Run the (mock) pipeline in-process. Demo/dev only — blocks a thread."""

    def __init__(self, storage: Storage, store: JobStore, pipeline_mode: str = "mock"):
        self.storage = storage
        self.store = store
        self.pipeline_mode = pipeline_mode

    def dispatch(
        self, job_id: str, video_key: str, metadata: dict | None, quality: str = "balanced"
    ) -> None:
        thread = threading.Thread(
            target=self._run, args=(job_id, video_key, metadata, quality), daemon=True
        )
        thread.start()

    def _run(self, job_id: str, video_key: str, metadata: dict | None, quality: str) -> None:
        import tempfile
        from pathlib import Path

        from spatialscan_worker.pipeline import JobSpec, run_pipeline

        try:
            with tempfile.TemporaryDirectory(prefix=f"spatialscan-{job_id}-") as tmp:
                tmp_path = Path(tmp)
                video_path = tmp_path / "input.mp4"
                video_path.write_bytes(self.storage.get_bytes(video_key))

                spec = JobSpec(
                    job_id=job_id,
                    video_path=video_path,
                    output_dir=tmp_path / "out",
                    metadata=metadata,
                    pipeline_mode=self.pipeline_mode,
                    quality=quality,
                )
                result = run_pipeline(
                    spec,
                    report=lambda stage, p: self.store.update(
                        job_id, status="processing", stage=stage, progress=p
                    ),
                )
                self.storage.put_bytes(
                    f"jobs/{job_id}/scene.splat",
                    result.splat_path.read_bytes(),
                    "application/octet-stream",
                )
                self.storage.put_bytes(
                    f"jobs/{job_id}/manifest.json",
                    result.manifest_path.read_bytes(),
                    "application/json",
                )
            self.store.update(
                job_id,
                status="done",
                stage="export",
                progress=1.0,
                manifest=json.dumps(result.manifest),
            )
        except Exception as exc:
            log.exception("inline job %s failed", job_id)
            self.store.update(job_id, status="error", error=str(exc))


class RedisQueueTrigger:
    def __init__(self, storage: Storage, redis_client: redis.Redis):
        self.storage = storage
        self.r = redis_client

    def dispatch(
        self, job_id: str, video_key: str, metadata: dict | None, quality: str = "balanced"
    ) -> None:
        payload = build_payload(job_id, video_key, metadata, self.storage, quality)
        self.r.lpush(QUEUE_KEY, json.dumps(payload))


class RunPodTrigger:
    def __init__(self, storage: Storage, store: JobStore, api_key: str, endpoint_id: str):
        if not api_key or not endpoint_id:
            raise ValueError("JOB_TRIGGER=runpod requires RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID")
        self.storage = storage
        self.store = store
        self.api_key = api_key
        self.base = f"https://api.runpod.ai/v2/{endpoint_id}"

    def dispatch(
        self, job_id: str, video_key: str, metadata: dict | None, quality: str = "balanced"
    ) -> None:
        payload = build_payload(job_id, video_key, metadata, self.storage, quality)
        resp = httpx.post(
            f"{self.base}/run",
            json={"input": payload},
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        self.store.set_runpod_id(job_id, resp.json()["id"])

    def fetch_status(self, runpod_job_id: str) -> dict:
        """Map RunPod job status onto our job-hash fields."""
        resp = httpx.get(
            f"{self.base}/status/{runpod_job_id}",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        rp_status = data.get("status", "")
        if rp_status in ("IN_QUEUE",):
            return {"status": "queued"}
        if rp_status in ("IN_PROGRESS",):
            progress = (data.get("output") or {}) if isinstance(data.get("output"), dict) else {}
            return {
                "status": "processing",
                "stage": progress.get("stage", "training"),
                "progress": progress.get("progress", 0.0),
            }
        if rp_status == "COMPLETED":
            manifest = ((data.get("output") or {}).get("manifest")) or {}
            return {
                "status": "done",
                "stage": "export",
                "progress": 1.0,
                "manifest": json.dumps(manifest),
            }
        return {"status": "error", "error": f"RunPod status {rp_status}"}


def build_trigger(
    settings: Settings, storage: Storage, store: JobStore, redis_client: redis.Redis
) -> JobTrigger:
    if settings.job_trigger == "inline":
        return InlineTrigger(storage, store)
    if settings.job_trigger == "redis":
        return RedisQueueTrigger(storage, redis_client)
    if settings.job_trigger == "runpod":
        return RunPodTrigger(
            storage, store, settings.runpod_api_key, settings.runpod_endpoint_id
        )
    raise ValueError(f"unknown JOB_TRIGGER '{settings.job_trigger}' (inline|redis|runpod)")
