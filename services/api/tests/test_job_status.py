from spatialscan_api.jobs.store import JobStore


def test_unknown_job_404(noop_client):
    resp = noop_client.get("/api/jobs/doesnotexist")
    assert resp.status_code == 404


def test_unknown_tour_404(noop_client):
    resp = noop_client.get("/api/tours/doesnotexist")
    assert resp.status_code == 404


def test_store_stage_transitions(redis_client):
    store = JobStore(redis_client)
    job_id = store.new_job_id()
    store.create(job_id, f"jobs/{job_id}/input.mp4", {"duration_sec": 10})

    job = store.get(job_id)
    assert job["status"] == "queued"
    assert job["stage"] == "upload"

    store.update(job_id, status="processing", stage="training", progress=0.55)
    job = store.get(job_id)
    assert job["status"] == "processing"
    assert float(job["progress"]) == 0.55

    store.update(job_id, status="error", error="colmap found no poses")
    job = store.get(job_id)
    assert job["status"] == "error"
    assert "colmap" in job["error"]


def test_error_surfaces_in_api(noop_client, redis_client):
    from conftest import upload_video

    job_id = upload_video(noop_client).json()["job_id"]
    JobStore(redis_client).update(job_id, status="error", error="boom")
    status = noop_client.get(f"/api/jobs/{job_id}").json()
    assert status["status"] == "error"
    assert status["error"] == "boom"
    assert status["tour_url"] is None


def test_healthz(noop_client):
    resp = noop_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
