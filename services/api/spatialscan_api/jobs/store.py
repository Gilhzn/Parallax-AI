"""Job state in Redis: one hash per job (``job:{id}``) with a 7-day TTL.

The queue worker writes to the same hashes (same Redis), so status polling is
a plain read. Durable results live next to the ``.splat`` as
``manifest.json`` in object storage — Redis is disposable.
"""

from __future__ import annotations

import json
import time
import uuid

import redis

JOB_TTL_SEC = 7 * 24 * 3600


class JobStore:
    def __init__(self, client: redis.Redis):
        self.r = client

    @staticmethod
    def new_job_id() -> str:
        return uuid.uuid4().hex[:12]

    def _key(self, job_id: str) -> str:
        return f"job:{job_id}"

    def create(self, job_id: str, video_key: str, metadata: dict | None) -> None:
        self.r.hset(
            self._key(job_id),
            mapping={
                "status": "queued",
                "stage": "upload",
                "progress": 0.0,
                "video_key": video_key,
                "metadata": json.dumps(metadata or {}),
                "created_at": time.time(),
            },
        )
        self.r.expire(self._key(job_id), JOB_TTL_SEC)

    def get(self, job_id: str) -> dict | None:
        data = self.r.hgetall(self._key(job_id))
        if not data:
            return None
        # fakeredis/redis may return bytes depending on decode_responses.
        return {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in data.items()
        }

    def update(self, job_id: str, **fields) -> None:
        self.r.hset(self._key(job_id), mapping=fields)
        self.r.expire(self._key(job_id), JOB_TTL_SEC)

    def set_runpod_id(self, job_id: str, runpod_job_id: str) -> None:
        self.update(job_id, runpod_job_id=runpod_job_id)
