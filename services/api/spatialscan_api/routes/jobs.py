from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import ValidationError

from ..models import JobCreateResponse, JobStatusResponse, TourResponse, VideoMetadata

router = APIRouter(prefix="/api")

_ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}


@router.post("/jobs", response_model=JobCreateResponse, status_code=201)
async def create_job(
    request: Request,
    video: UploadFile = File(...),
    metadata: str = Form("{}"),
) -> JobCreateResponse:
    settings = request.app.state.settings
    storage = request.app.state.storage
    store = request.app.state.job_store
    trigger = request.app.state.trigger

    if video.content_type not in _ALLOWED_VIDEO_TYPES and not (
        video.filename or ""
    ).lower().endswith((".mp4", ".mov", ".webm")):
        raise HTTPException(415, f"unsupported video type '{video.content_type}'")

    try:
        meta = VideoMetadata.model_validate_json(metadata)
    except ValidationError as exc:
        raise HTTPException(422, f"invalid metadata: {exc.errors()[0]['msg']}") from exc

    if meta.duration_sec > settings.max_video_seconds:
        raise HTTPException(
            413,
            f"video is {meta.duration_sec:.0f}s; MVP limit is {settings.max_video_seconds}s",
        )

    data = await video.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(413, f"upload exceeds {settings.max_upload_mb}MB limit")
    if not data:
        raise HTTPException(422, "empty video upload")

    job_id = store.new_job_id()
    video_key = f"jobs/{job_id}/input.mp4"
    storage.put_bytes(video_key, data, video.content_type or "video/mp4")
    store.create(job_id, video_key, meta.model_dump())
    trigger.dispatch(job_id, video_key, meta.model_dump())
    return JobCreateResponse(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, request: Request) -> JobStatusResponse:
    store = request.app.state.job_store
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")

    # In RunPod mode, refresh live status from the serverless endpoint.
    trigger = request.app.state.trigger
    runpod_job_id = job.get("runpod_job_id")
    if runpod_job_id and job.get("status") not in ("done", "error") and hasattr(
        trigger, "fetch_status"
    ):
        updates = trigger.fetch_status(runpod_job_id)
        store.update(job_id, **updates)
        job.update({k: str(v) for k, v in updates.items()})

    status = job.get("status", "queued")
    return JobStatusResponse(
        job_id=job_id,
        status=status,
        stage=job.get("stage"),
        progress=float(job.get("progress", 0.0)),
        error=job.get("error"),
        tour_url=f"/tour/{job_id}" if status == "done" else None,
    )


@router.get("/tours/{job_id}", response_model=TourResponse)
def get_tour(job_id: str, request: Request) -> TourResponse:
    storage = request.app.state.storage
    manifest_key = f"jobs/{job_id}/manifest.json"
    splat_key = f"jobs/{job_id}/scene.splat"
    try:
        manifest = json.loads(storage.get_bytes(manifest_key))
    except KeyError:
        raise HTTPException(404, "tour not found (job may still be processing)") from None
    if not storage.exists(splat_key):
        raise HTTPException(404, "tour scene file missing")
    return TourResponse(job_id=job_id, splat_url=storage.url_for(splat_key), manifest=manifest)
