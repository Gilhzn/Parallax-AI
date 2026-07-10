import sys
from pathlib import Path

import fakeredis
import pytest
from fastapi.testclient import TestClient

# Make the worker package importable when running from a source checkout
# (InlineTrigger imports spatialscan_worker for the mock pipeline).
_WORKER_SRC = Path(__file__).resolve().parents[2] / "worker"
if str(_WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(_WORKER_SRC))

from spatialscan_api.config import Settings  # noqa: E402
from spatialscan_api.jobs.store import JobStore  # noqa: E402
from spatialscan_api.jobs.trigger import InlineTrigger  # noqa: E402
from spatialscan_api.main import create_app  # noqa: E402
from spatialscan_api.storage.local import LocalDiskStorage  # noqa: E402


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def storage(tmp_path):
    return LocalDiskStorage(str(tmp_path / "storage"), "http://testserver")


@pytest.fixture
def settings():
    return Settings(
        storage_backend="local",
        job_trigger="inline",
        max_video_seconds=45,
        max_upload_mb=10,
    )


@pytest.fixture
def client(settings, redis_client, storage):
    app = create_app(
        settings=settings,
        redis_client=redis_client,
        storage=storage,
        trigger=InlineTrigger(storage, JobStore(redis_client), pipeline_mode="mock"),
    )
    return TestClient(app)


@pytest.fixture
def noop_client(settings, redis_client, storage):
    """Client whose trigger does nothing — for testing pre-pipeline states."""

    class NoopTrigger:
        dispatched: list = []

        def dispatch(self, job_id, video_key, metadata):
            self.dispatched.append((job_id, video_key, metadata))

    app = create_app(
        settings=settings, redis_client=redis_client, storage=storage, trigger=NoopTrigger()
    )
    return TestClient(app)


