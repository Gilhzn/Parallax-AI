from typing import Literal

from pydantic import BaseModel, Field


class VideoMetadata(BaseModel):
    """Best-effort capture metadata extracted by the client before upload."""

    duration_sec: float = Field(gt=0)
    width: int | None = None
    height: int | None = None
    fps: float | None = None  # browsers don't expose FPS; estimated client-side
    size_bytes: int | None = None


class JobCreateResponse(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "done", "error"]
    stage: str | None = None
    progress: float = 0.0
    error: str | None = None
    tour_url: str | None = None


class TourResponse(BaseModel):
    job_id: str
    splat_url: str
    manifest: dict
