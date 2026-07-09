"""Dev entrypoint: consume jobs from a Redis list and update job hashes.

Run with::

    REDIS_URL=redis://localhost:6379/0 python -m spatialscan_worker.queue_worker

The API's RedisQueueTrigger LPUSHes JSON payloads (see
:func:`spatialscan_worker.pipeline.process_payload` for the shape) onto
``spatialscan:jobs``; job state lives in the ``job:{id}`` hash that the API
reads back for status polling.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time

import redis

from .pipeline import process_payload

QUEUE_KEY = "spatialscan:jobs"
JOB_TTL_SEC = 7 * 24 * 3600

log = logging.getLogger("spatialscan.worker")


def handle_job(r: redis.Redis, payload: dict) -> None:
    job_id = payload["job_id"]
    job_key = f"job:{job_id}"

    def report(stage: str, progress: float) -> None:
        r.hset(job_key, mapping={"status": "processing", "stage": stage, "progress": progress})
        r.expire(job_key, JOB_TTL_SEC)

    try:
        manifest = process_payload(payload, report=report)
        r.hset(
            job_key,
            mapping={
                "status": "done",
                "stage": "export",
                "progress": 1.0,
                "manifest": json.dumps(manifest),
            },
        )
        log.info("job %s done (%s bytes)", job_id, manifest.get("size_bytes"))
    except Exception as exc:
        log.exception("job %s failed", job_id)
        r.hset(job_key, mapping={"status": "error", "error": str(exc)})
    finally:
        r.expire(job_key, JOB_TTL_SEC)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    log.info("queue worker listening on %s (%s)", QUEUE_KEY, redis_url)
    while True:
        try:
            item = r.brpop(QUEUE_KEY, timeout=5)
        except redis.ConnectionError:
            log.warning("redis unavailable, retrying in 3s")
            time.sleep(3)
            continue
        if item is None:
            continue
        _, raw = item
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            log.error("dropping malformed payload: %.200s", raw)
            continue
        handle_job(r, payload)


if __name__ == "__main__":
    sys.exit(main())
