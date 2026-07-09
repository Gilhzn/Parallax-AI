import json
from pathlib import Path

from spatialscan_worker.pipeline import STAGES, JobSpec, run_pipeline
from spatialscan_worker.splat_format import read_splat, splat_count


def test_mock_pipeline_end_to_end(tiny_mp4: Path, tmp_path: Path):
    events: list[tuple[str, float]] = []
    spec = JobSpec(
        job_id="test123",
        video_path=tiny_mp4,
        output_dir=tmp_path / "out",
        metadata={"duration_sec": 12, "width": 1280, "height": 720},
        pipeline_mode="mock",
        splat_max_mb=40,
    )
    result = run_pipeline(spec, report=lambda stage, p: events.append((stage, p)))

    # Valid, budget-respecting splat output.
    data = result.splat_path.read_bytes()
    n = splat_count(data)
    assert n > 100
    assert len(data) < 40 * 1024 * 1024
    cloud = read_splat(data)
    assert len(cloud) == n

    # Manifest is written and consistent.
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["job_id"] == "test123"
    assert manifest["splat_count"] == n
    assert manifest["size_bytes"] == len(data)
    assert manifest["pipeline_mode"] == "mock"
    assert manifest["frame_count"] >= 12 * 3  # duration * fps

    # Every stage reported, progress monotonic, ends at 1.0.
    assert {s for s, _ in events} == set(STAGES)
    progresses = [p for _, p in events]
    assert progresses == sorted(progresses)
    assert progresses[-1] == 1.0


def test_mock_pipeline_without_metadata(tiny_mp4: Path, tmp_path: Path):
    spec = JobSpec(
        job_id="nometa",
        video_path=tiny_mp4,
        output_dir=tmp_path / "out",
        pipeline_mode="mock",
    )
    result = run_pipeline(spec)
    assert result.splat_path.exists()
    assert result.manifest["frame_count"] >= 4
