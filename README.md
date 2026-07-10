# SpatialScan

**Turn a 45-second smartphone video into a photorealistic, walkable 3D virtual tour** — powered by 3D Gaussian Splatting, serverless GPUs, and a plain web browser. No LiDAR rig, no Matterport camera, no idle GPU bills.

> 🇮🇱 מסמך האיפיון הראשי בעברית: [docs/PRD.he.md](docs/PRD.he.md) · English PRD: [docs/PRD.en.md](docs/PRD.en.md)

**🔗 Live demo:** <https://gilhzn.github.io/Parallax-AI/> — the full web app in *demo mode* (no GPU backend attached): upload any short video to see the simulated pipeline, or jump straight into the [sample 3D tour](https://gilhzn.github.io/Parallax-AI/tour/sample). Deployed automatically to GitHub Pages on every push (`.github/workflows/pages.yml`).

**🎥 Reconstruct YOUR video — free, no GPU, no extra accounts:** upload a video into [`captures/`](captures/) (GitHub web: *Add file → Upload files*) or run the **"Reconstruct video"** workflow from the Actions tab with a video URL. It runs REAL structure-from-motion (COLMAP) + Gaussian Splatting training (OpenSplat, CPU) on GitHub's free runners and publishes a walkable tour of your actual footage to `…/tour/<name>`. Expect 1–3 hours and preview-grade quality; the GPU paths in [docs/QUALITY.md](docs/QUALITY.md) give full quality in minutes.

## How it works

```
[ Phone browser (PWA) ] ──(MP4 + metadata JSON)──▶ [ FastAPI gateway ]
                                                        │
                                              job queue (Redis) ── dev
                                              RunPod Serverless ── prod
                                                        │
[ Browser: 3D first-person tour ] ◀──(.splat)── [ GPU worker: ffmpeg → COLMAP → 3DGS → export ]
```

1. **Capture** — the web app records/accepts a video (≤45s), extracts metadata (duration, resolution, estimated FPS) and uploads it.
2. **Process** — a GPU worker extracts frames (~3 fps), recovers camera poses with COLMAP, trains a 3D Gaussian Splatting model (~5,000 iterations, minutes on a modern GPU), and exports a compact `.splat` file (<40 MB).
3. **Tour** — a Three.js viewer loads the `.splat` progressively and renders a walkable, photorealistic space at 60 FPS on mobile browsers.

## Repository map

| Path | What it is |
|---|---|
| `apps/web/` | Vite + React + TypeScript PWA — upload flow, job progress, 3D splat viewer |
| `services/api/` | FastAPI gateway — uploads, job store (Redis), storage (local/S3/R2), worker triggers |
| `services/worker/` | Python GPU pipeline — one `run_pipeline()`, three entrypoints (queue / RunPod / CLI) |
| `scripts/` | Utilities (e.g. generate the synthetic sample `.splat`) |
| `notebooks/` | Google Colab notebook — run the real pipeline on a **free T4 GPU** |
| `infra/` | RunPod endpoint + deployment notes (Cloudflare Pages / R2, Fly.io) |
| `docs/` | PRD (he/en), architecture, team skills, free-tier testing guide |

## Quickstart (no GPU required)

The whole flow runs locally in **mock mode**: the pipeline produces a synthetic room `.splat` so you can exercise upload → queue → processing → viewer end-to-end on any laptop.

```bash
# 1. API (serves the pipeline inline, stores files on local disk)
make api-install
make demo          # uvicorn on :8000 with InlineTrigger + local storage

# 2. Web app (separate terminal)
make web-install
make web-dev       # vite on :5173, proxies /api and /media to :8000
```

Open http://localhost:5173, upload any short MP4, watch the job progress, then walk through the generated tour. A committed demo scene is also available at `/tour/sample`.

### With Docker (redis + minio + api + mock worker)

```bash
docker compose up --build
```

### Tests

```bash
make test          # pytest (api + worker) + vitest + builds
make lint          # ruff + eslint
```

## Running the *real* pipeline (GPU)

This container/laptop path is mock-only. For real reconstructions:

- **Free (testing):** open [`notebooks/spatialscan_worker_colab.ipynb`](notebooks/spatialscan_worker_colab.ipynb) in Google Colab (free T4 GPU) — it installs COLMAP + gsplat and runs `python -m spatialscan_worker.cli` on your video. See [docs/FREE_TIER_TESTING.md](docs/FREE_TIER_TESTING.md).
- **Production (cheapest):** deploy `services/worker/Dockerfile` as a **RunPod Serverless** endpoint — GPUs wake per job, bill per second, and scale to zero. See [infra/runpod/endpoint.md](infra/runpod/endpoint.md).

## Environment matrix

| | Storage | Trigger | Pipeline |
|---|---|---|---|
| **Local demo** | local disk | `inline` (background thread) | `mock` |
| **docker-compose** | MinIO (S3 API) | `redis` queue | `mock` |
| **Colab / GCP VM** | local paths (CLI) | manual | `real` |
| **Production** | Cloudflare R2 | `runpod` (serverless HTTP) | `real` |

All switches are environment variables — see [.env.example](.env.example).

## Documentation

- [docs/PRD.he.md](docs/PRD.he.md) — מסמך איפיון (עברית, ראשי)
- [docs/PRD.en.md](docs/PRD.en.md) — Product Requirements (English)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system architecture & data flow
- [docs/TEAM_SKILLS.md](docs/TEAM_SKILLS.md) — the skillset needed to build/extend this
- [docs/QUALITY.md](docs/QUALITY.md) — quality presets; how to reconstruct at **full resolution with no compromises**
- [docs/FREE_TIER_TESTING.md](docs/FREE_TIER_TESTING.md) — free GPU testing (Colab / GCP credits)

## License

Proprietary — all rights reserved (MVP stage).
