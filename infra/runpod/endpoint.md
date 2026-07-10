# RunPod Serverless Endpoint — Production Worker

The production GPU tier: containers wake per job, bill per second, scale to zero. No idle GPU costs — the core of the cost model.

## 1. Build & push the image

```bash
docker build -t <registry>/spatialscan-worker:latest -f services/worker/Dockerfile services/worker
docker push <registry>/spatialscan-worker:latest
```

(Any registry RunPod can pull from: Docker Hub, GHCR, etc.)

## 2. Create the endpoint (RunPod console → Serverless → New Endpoint)

| Setting | Value | Why |
|---|---|---|
| Container image | `<registry>/spatialscan-worker:latest` | Runs `python3 -m spatialscan_worker.runpod_handler` |
| GPU types | RTX 4090 (primary), RTX A5000/3090 (fallback) | 4090 ≈ $0.00019/s; a 45s-video job ≈ 3–5 min ≈ **$0.03–0.06** |
| Min workers | **0** | Scale to zero — the whole point |
| Max workers | 2–3 for MVP | Cap burst spend |
| Idle timeout | 30–60s | Absorbs bursts without cold-starting every job |
| Execution timeout | 3600s | `quality=high` (30k iterations, full resolution) needs up to ~30 min on a 4090 |
| Container disk | 30GB | Model weights + COLMAP workspace |
| Env vars | `PIPELINE_MODE=real` (quality arrives per job in the payload; see docs/QUALITY.md) | Same knobs as everywhere else |

No storage credentials on the endpoint — jobs arrive with presigned GET/PUT URLs.

## 3. Wire the API to it

In the API service environment:

```
JOB_TRIGGER=runpod
RUNPOD_API_KEY=<from RunPod settings>
RUNPOD_ENDPOINT_ID=<endpoint id>
```

The API POSTs `{"input": {job_id, video_url, splat_put_url, manifest_put_url, metadata}}` to `https://api.runpod.ai/v2/{endpoint}/run` and maps `/status/{id}` responses onto job status (see `spatialscan_api/jobs/trigger.py::RunPodTrigger`).

## 4. Smoke test

```bash
curl -X POST "https://api.runpod.ai/v2/$ENDPOINT/run" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" -H "Content-Type: application/json" \
  -d '{"input": {"job_id": "smoke1", "video_url": "<presigned GET>", "splat_put_url": "<presigned PUT>", "manifest_put_url": "<presigned PUT>", "metadata": {"duration_sec": 20}}}'
```

Then poll `/status/{id}` until `COMPLETED` and confirm the `.splat` landed in the bucket.

## Cost guardrails

- Alert if GPU-seconds/job drifts above ~400s (misconfigured training or COLMAP thrash).
- `TRAIN_ITERATIONS` is the main quality/cost dial; 5,000 is the MVP sweet spot.
- Cold start (image pull + CUDA init) ≈ 30–60s on first job after idle — acceptable at MVP; keep-warm (min workers 1) only when volume justifies it.
