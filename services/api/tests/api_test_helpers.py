"""Shared helpers for API tests (unique module name — two `tests/` trees
live on sys.path, so a shared `conftest` import would be ambiguous)."""

# Minimal MP4 container: an 'ftyp' box plus a 'free' box. Enough for anything
# that sniffs magic bytes; the mock pipeline never decodes the stream.
TINY_MP4 = (
    b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    b"\x00\x00\x00\x08free"
)


def upload_video(client, duration_sec=12.0, data=TINY_MP4, content_type="video/mp4"):
    return client.post(
        "/api/jobs",
        files={"video": ("clip.mp4", data, content_type)},
        data={
            "metadata": (
                f'{{"duration_sec": {duration_sec}, "width": 1280, '
                f'"height": 720, "fps": 30, "size_bytes": {len(data)}}}'
            )
        },
    )
