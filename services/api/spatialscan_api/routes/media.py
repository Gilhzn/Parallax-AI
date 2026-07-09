"""Dev-only media routes backing :class:`LocalDiskStorage` URLs.

GET serves stored objects to the browser/worker; PUT accepts worker result
uploads (the local stand-in for S3 presigned PUTs). Mounted only when
``STORAGE_BACKEND=local`` — in production, media lives on R2/S3 and never
touches the API.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

router = APIRouter()

_CONTENT_TYPES = {
    ".splat": "application/octet-stream",
    ".json": "application/json",
    ".mp4": "video/mp4",
}


@router.get("/media/{key:path}")
def get_media(key: str, request: Request) -> Response:
    storage = request.app.state.storage
    try:
        data = storage.get_bytes(key)
    except (KeyError, ValueError):
        raise HTTPException(404, "not found") from None
    suffix = "." + key.rsplit(".", 1)[-1] if "." in key else ""
    return Response(
        content=data,
        media_type=_CONTENT_TYPES.get(suffix, "application/octet-stream"),
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.put("/media/{key:path}")
async def put_media(key: str, request: Request) -> dict:
    storage = request.app.state.storage
    data = await request.body()
    try:
        storage.put_bytes(key, data, request.headers.get("content-type", "application/octet-stream"))
    except ValueError:
        raise HTTPException(400, "invalid key") from None
    return {"stored": key, "bytes": len(data)}
