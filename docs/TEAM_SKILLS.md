# SpatialScan — Team & Skills Profile / פרופיל צוות וכישורים

The exact skillset needed to build and scale this product — whether you develop it yourself or hire.
הכישורים המדויקים הנדרשים להקמה והרחבה של המוצר — בין אם אתה מפתח בעצמך ובין אם מגייס.

The MVP in this repo maps to these three roles; each section lists where their code lives.

---

## 1. AI / Computer Vision Engineer — מהנדס ליבה

**Role · תפקיד:** owns the pipeline that turns video into a 3D model.
בעלות על הפייפליין שהופך וידאו למודל תלת-ממד.

**Critical skills · כישורים קריטיים:**
- Full command of **Python** and deep-learning stacks (**PyTorch**).
- Hands-on experience with **3D Gaussian Splatting**: the original INRIA implementation, **gsplat**, and **Nerfstudio** (`splatfacto`). Understanding of the training loop: densification, opacity reset, SH degrees, pruning.
- **COLMAP** / Structure-from-Motion: feature extraction, matching, sparse reconstruction; diagnosing pose-recovery failures (textureless walls, motion blur, rolling shutter).
- **ffmpeg** and video fundamentals (keyframes, exposure, rolling shutter effects on SfM).
- Splat/point-cloud post-processing: pruning, compression, format conversion (PLY ↔ .splat), meshing (SuGaR / Poisson) as a phase-2 skill.

**Their code here · הקוד שלהם בריפו:** `services/worker/spatialscan_worker/` — `stages/`, `ply_io.py`, `splat_format.py`, `synthetic.py`.

---

## 2. Backend & DevOps Engineer — ארכיטקט שרתים ואינטגרציה

**Role · תפקיד:** connects mobile clients to the serverless GPU fleet; owns queues, storage, and cost control.
חיבור הלקוחות למערך ה-GPU, ניהול תורים, אחסון ושליטה בעלויות.

**Critical skills · כישורים קריטיים:**
- Fast async APIs in **Python (FastAPI)** — uploads, polling, presigned-URL flows.
- **Docker** for AI workloads: CUDA base images, COLMAP/nerfstudio system deps, image-size discipline.
- Async job systems: Redis queues (this MVP), and when to graduate to Celery/RabbitMQ/SQS.
- **Serverless GPU providers**: RunPod Serverless API (`/run`, `/status`), cold-start economics, scale-to-zero configuration; alternatives (Modal, JarvisLabs, Replicate).
- S3-compatible object storage (**Cloudflare R2**, MinIO, AWS S3): presigned URLs, CORS, lifecycle rules, egress-cost awareness.
- Observability: job-level tracing, GPU-seconds per job as the core cost metric.

**Their code here · הקוד שלהם בריפו:** `services/api/`, `services/worker/{queue_worker,runpod_handler,pipeline}.py`, `docker-compose.yml`, `infra/`, `.github/workflows/`.

---

## 3. Frontend & 3D Web Engineer — מפתח ממשק ומנוע תצוגה

**Role · תפקיד:** owns the capture UX and the in-browser 3D experience.
בעלות על חוויית הצילום ועל חוויית התלת-ממד בדפדפן.

**Critical skills · כישורים קריטיים:**
- **TypeScript + React** (this MVP), PWA fundamentals (manifest, installability; service workers in phase 2).
- **Three.js** at the render-loop level: cameras, quaternions, pointer events — not just `<Canvas>` components. (R3F is deliberately *not* used here: splat renderers own their loop.)
- Gaussian-splat web renderers: `@mkkellogg/gaussian-splats-3d` internals — progressive loading, sort workers, COOP/COEP tradeoffs (SharedArrayBuffer), alpha-removal thresholds, scene reveal modes.
- **Mobile 60 FPS discipline:** devicePixelRatio caps, splat-count budgets, profiling on real iOS Safari / Android Chrome, motion-sickness-aware camera design (fixed eye height, clamped pitch).
- Media APIs: `MediaRecorder` / camera capture inputs, `requestVideoFrameCallback`, object URLs, multipart uploads with progress.
- Phase 2: **Flutter or React Native** for the native capture app (guided-capture overlays, gyroscope hints) over the same API.

**Their code here · הקוד שלהם בריפו:** `apps/web/src/` — `viewer/SplatViewer.tsx`, `viewer/FirstPersonControls.ts`, `lib/videoMetadata.ts`, `pages/`.

---

## Hiring order · סדר גיוס מומלץ

1. **Backend/DevOps first** — the serverless-GPU cost model is the business moat; it must be solid before scale.
2. **CV engineer second** — quality of reconstruction is the product; tune COLMAP/3DGS parameters per real-world footage.
3. **Frontend third** — the MVP viewer works; a specialist takes it from functional to delightful (guided capture, editor tools).

For a solo founder: this repo is ordered so one person can wear the hats in that same order — the mock pipeline keeps the frontend and backend unblocked while the CV work matures.
