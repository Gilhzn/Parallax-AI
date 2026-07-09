"""Production entrypoint: RunPod Serverless handler.

The Docker image (see ``Dockerfile``) starts this module; RunPod invokes
``handler`` once per queued job and bills only for execution seconds. The
payload uses presigned URLs, so the GPU container holds no storage
credentials. Progress is surfaced through RunPod's progress-update API and
mirrored by the SpatialScan API's status proxy.
"""

from __future__ import annotations

from .pipeline import process_payload


def handler(event: dict) -> dict:
    import runpod  # imported lazily: only installed in the GPU image

    payload = event["input"]

    def report(stage: str, progress: float) -> None:
        runpod.serverless.progress_update(event, {"stage": stage, "progress": progress})

    manifest = process_payload(payload, report=report)
    return {"status": "done", "manifest": manifest}


def main() -> None:
    import runpod

    runpod.serverless.start({"handler": handler})


if __name__ == "__main__":
    main()
