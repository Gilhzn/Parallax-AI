import pytest

from spatialscan_api.storage.local import LocalDiskStorage


def test_local_round_trip(tmp_path):
    s = LocalDiskStorage(str(tmp_path), "http://localhost:8000")
    s.put_bytes("jobs/abc/scene.splat", b"\x01\x02\x03")
    assert s.exists("jobs/abc/scene.splat")
    assert s.get_bytes("jobs/abc/scene.splat") == b"\x01\x02\x03"
    assert s.url_for("jobs/abc/scene.splat") == "http://localhost:8000/media/jobs/abc/scene.splat"
    assert s.presign_get("k") == s.presign_put("k")  # plain URLs in local mode


def test_local_missing_key(tmp_path):
    s = LocalDiskStorage(str(tmp_path), "http://localhost:8000")
    assert not s.exists("nope")
    with pytest.raises(KeyError):
        s.get_bytes("nope")


def test_local_path_traversal_blocked(tmp_path):
    s = LocalDiskStorage(str(tmp_path / "root"), "http://localhost:8000")
    with pytest.raises(ValueError):
        s.put_bytes("../escape.txt", b"x")
    with pytest.raises(ValueError):
        s.get_bytes("../../etc/passwd")


def test_media_routes_round_trip(noop_client):
    put = noop_client.put("/media/jobs/xyz/scene.splat", content=b"\x00" * 64)
    assert put.status_code == 200
    got = noop_client.get("/media/jobs/xyz/scene.splat")
    assert got.status_code == 200
    assert got.content == b"\x00" * 64
    assert got.headers["content-type"] == "application/octet-stream"


def test_media_get_missing_404(noop_client):
    assert noop_client.get("/media/jobs/none/scene.splat").status_code == 404
