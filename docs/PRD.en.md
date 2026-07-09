# Product Requirements: SpatialScan Platform (MVP)

> גרסה בעברית (ראשית): [PRD.he.md](PRD.he.md) · Architecture: [ARCHITECTURE.md](ARCHITECTURE.md) · Team: [TEAM_SKILLS.md](TEAM_SKILLS.md)

## 1. Product Vision

SpatialScan is a SaaS platform that turns an ordinary smartphone video (up to 45 seconds) into a photorealistic, freely walkable 3D virtual tour rendered in any browser — no app install, no dedicated hardware.

**Competitive edge vs. Matterport:**

| | Matterport | SpatialScan |
|---|---|---|
| Hardware | Dedicated 360° camera (thousands of $) | Any smartphone |
| Technology | Photogrammetry / depth cameras | 3D Gaussian Splatting (3DGS) |
| Idle infrastructure cost | Always-on servers | **Zero** — serverless GPUs that sleep |
| Time to result | Hours (scan + processing) | Minutes |
| Viewing | Heavy viewer/app | Browser, progressive loading |

## 2. Cost Strategy (Free-Tier → Serverless)

The same pipeline code runs in three environments; switching is environment variables only:

1. **Development ($0):** `PIPELINE_MODE=mock` — the pipeline emits a synthetic scene, so the entire flow runs on any laptop without a GPU.
2. **Testing ($0):** Google Colab's free T4 GPU via the committed notebook, or a GCP VM on the $300 trial credit.
   ⚠️ **Correction:** a tool called `@googlecolab/cli` with commands like `colab new --gpu T4` **does not exist**. The real path is documented in [FREE_TIER_TESTING.md](FREE_TIER_TESTING.md) — a notebook that clones this repo and runs the worker CLI on Colab's GPU.
3. **Production (cheapest):** RunPod Serverless — a GPU container (e.g. RTX 4090) wakes only when a job is queued, bills per second of work, and scales to zero. Storage on Cloudflare R2 (zero egress fees).

## 3. System Architecture

```
[ Mobile browser (PWA) ] ──(MP4 + metadata JSON)──▶ [ API Gateway (FastAPI) ]
                                                          │
                                             job queue (Redis) ─── dev
                                             RunPod Serverless ─── prod
                                                          │
[ Browser: 3D tour ] ◀──(.splat)── [ Worker: ffmpeg → COLMAP → 3DGS → export ]
```

- **Storage:** S3-compatible object storage (Cloudflare R2 in prod, MinIO/local disk in dev). Raw video, the `.splat`, and `manifest.json` live under `jobs/{job_id}/`.
- **Worker security:** the worker receives **presigned URLs** only (GET for video, PUT for results) — the GPU container holds no storage credentials.
- **Job state:** one Redis hash per job with a 7-day TTL; the manifest in object storage is the durable record.

## 4. Functional Requirements (MVP)

### 4.1 Client module (Web/PWA)

| Requirement | Implementation |
|---|---|
| Capture/select video | `<input capture="environment">` — rear camera or existing file |
| Duration guardrail | Max **45 seconds**; enforced client-side pre-upload and again server-side |
| Metadata extraction | Duration + resolution from `loadedmetadata`; FPS estimated via `requestVideoFrameCallback` (browsers expose no FPS property — best-effort, `null` on failure) |
| Progress tracking | 2-second polling; five-stage stepper |
| Sharing | Tour link via Web Share API / clipboard |

### 4.2 Processing engine (Worker)

| Stage | Tool | Parameters |
|---|---|---|
| 1. Frame extraction | ffmpeg | ~3 fps (`FRAMES_PER_SECOND`) |
| 2. Camera recovery | COLMAP (via `ns-process-data`) | Structure-from-Motion → `transforms.json` |
| 3. 3DGS training | nerfstudio `splatfacto` (gsplat-backed) | ~5,000 iterations (`TRAIN_ITERATIONS`) — ~3 min on a modern GPU |
| 4. Export | internal PLY→splat converter | `.splat` format (antimatter15, 32 bytes/splat); opacity-based pruning to a **40MB** budget (`SPLAT_MAX_MB`) |

**Structural principle:** one pipeline (`run_pipeline()`), three entrypoints — Redis queue (dev), RunPod handler (prod), CLI (Colab/GCP). Every stage has a `real` and a `mock` implementation; `PIPELINE_MODE=auto` picks per stage based on installed tools.

### 4.3 Tour viewer (Web)

- **Rendering:** Three.js + `@mkkellogg/gaussian-splats-3d`.
- **Touch-first first-person navigation:** drag = look (yaw/pitch clamped to ±80°); tap = step forward at fixed eye height; pinch = dolly; mouse wheel on desktop.
- **Progressive loading:** the space appears blurry and sharpens within 2–3 seconds (`progressiveLoad`).
- **No COOP/COEP requirement:** `sharedMemoryForWorkers: false` — deployable on any static CDN.

## 5. Non-Functional Requirements

| Metric | Target |
|---|---|
| End-to-end time (upload → link) | **< 7 minutes** for an average space |
| Mobile FPS (iOS Safari / Android Chrome) | **60 FPS** — critical against motion sickness. Levers: splat budget at export, `devicePixelRatio` capped at 2, fixed eye height |
| Tour file size | < 40MB (MVP scenes ≈ 5–15MB in practice) |
| Result durability | manifest + splat in durable storage; Redis is disposable |

## 6. Out of MVP Scope

User accounts/auth, billing and quotas, native mobile app (phase 2 — Flutter/RN over the same API), multi-room stitching, scene editing, in-tour measurements, offline support.

## 7. MVP Success Metrics

1. A non-technical user produces a successful tour from their first video >80% of the time (guided by the UI).
2. Average processing cost per tour < $0.05 (RunPod 4090 ≈ $0.00019/s × ~4 minutes).
3. Tour load-to-interactive < 3 seconds on 4G.
