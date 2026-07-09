from __future__ import annotations

import logging

import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .jobs.store import JobStore
from .jobs.trigger import build_trigger
from .routes import jobs as jobs_routes
from .routes import media as media_routes
from .storage import build_storage
from .storage.base import Storage

log = logging.getLogger("spatialscan.api")


def build_redis(settings: Settings) -> redis.Redis:
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        client.ping()
        return client
    except redis.ConnectionError:
        if settings.job_trigger == "inline":
            # Zero-service demo mode: job state lives in-process.
            import fakeredis

            log.warning("redis unreachable — using in-process fakeredis (inline demo mode)")
            return fakeredis.FakeRedis(decode_responses=True)
        raise


def create_app(
    settings: Settings | None = None,
    redis_client: redis.Redis | None = None,
    storage: Storage | None = None,
    trigger=None,
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="SpatialScan API", version="0.1.0")

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    storage = storage or build_storage(settings)
    redis_client = redis_client if redis_client is not None else build_redis(settings)
    job_store = JobStore(redis_client)
    trigger = trigger or build_trigger(settings, storage, job_store, redis_client)

    app.state.settings = settings
    app.state.storage = storage
    app.state.job_store = job_store
    app.state.trigger = trigger

    app.include_router(jobs_routes.router)
    if settings.storage_backend == "local":
        app.include_router(media_routes.router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "trigger": settings.job_trigger, "storage": settings.storage_backend}

    return app


app = create_app()
