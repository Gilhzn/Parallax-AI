import sys
import time
from pathlib import Path

from conftest import TINY_MP4, upload_video

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "worker"))
from spatialscan_worker.splat_format import read_splat  # noqa: E402


def test_upload_creates_job_and_stores_video(noop_client, storage):
    resp = upload_video(noop_client)
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]
    assert resp.json()["status"] == "queued"
    assert storage.exists(f"jobs/{job_id}/input.mp4")
    assert storage.get_bytes(f"jobs/{job_id}/input.mp4") == TINY_MP4

    status = noop_client.get(f"/api/jobs/{job_id}").json()
    assert status["status"] == "queued"
    assert status["stage"] == "upload"


def test_full_inline_flow_upload_to_tour(client):
    resp = upload_video(client)
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]

    # Inline trigger runs the mock pipeline in a background thread.
    deadline = time.time() + 15
    status = None
    while time.time() < deadline:
        status = client.get(f"/api/jobs/{job_id}").json()
        if status["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert status is not None and status["status"] == "done", f"job stuck: {status}"
    assert status["progress"] == 1.0
    assert status["tour_url"] == f"/tour/{job_id}"

    tour = client.get(f"/api/tours/{job_id}")
    assert tour.status_code == 200
    body = tour.json()
    assert body["manifest"]["job_id"] == job_id
    assert body["manifest"]["splat_count"] > 100

    # The splat URL is servable and contains valid splat bytes.
    splat_path = body["splat_url"].replace("http://testserver", "")
    splat = client.get(splat_path)
    assert splat.status_code == 200
    cloud = read_splat(splat.content)
    assert len(cloud) == body["manifest"]["splat_count"]


def test_rejects_video_over_duration_limit(noop_client):
    resp = upload_video(noop_client, duration_sec=90.0)
    assert resp.status_code == 413
    assert "45s" in resp.json()["detail"]


def test_rejects_oversized_upload(noop_client):
    big = b"\x00" * (11 * 1024 * 1024)  # limit in test settings is 10MB
    resp = upload_video(noop_client, data=big)
    assert resp.status_code == 413


def test_rejects_non_video(noop_client):
    resp = noop_client.post(
        "/api/jobs",
        files={"video": ("notes.txt", b"hello", "text/plain")},
        data={"metadata": '{"duration_sec": 5}'},
    )
    assert resp.status_code == 415


def test_rejects_bad_metadata(noop_client):
    resp = noop_client.post(
        "/api/jobs",
        files={"video": ("clip.mp4", TINY_MP4, "video/mp4")},
        data={"metadata": "not json"},
    )
    assert resp.status_code == 422
