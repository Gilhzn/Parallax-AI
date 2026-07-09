from pathlib import Path

import pytest

# Minimal MP4 container: an 'ftyp' box plus a 'free' box. Enough for anything
# that sniffs magic bytes; the mock pipeline never decodes the stream.
TINY_MP4 = (
    b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    b"\x00\x00\x00\x08free"
)


@pytest.fixture
def tiny_mp4(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.mp4"
    path.write_bytes(TINY_MP4)
    return path
