# Production Deployment Notes

Cheapest solid stack for the MVP. Everything here is config, not code — the repo already supports all of it via env vars.

## Topology

| Component | Host | Cost |
|---|---|---|
| Web app (`apps/web`) | Cloudflare Pages | free tier |
| API (`services/api`) | Fly.io / Railway (1 small instance) | ~$5/mo |
| Redis (job state + TTL) | Upstash / Fly Redis | free tier at MVP volume |
| Object storage | Cloudflare R2 | free tier 10GB, **zero egress fees** (tours are egress-heavy) |
| GPU workers | RunPod Serverless | per-second, scale-to-zero — see [runpod/endpoint.md](runpod/endpoint.md) |

## Cloudflare R2

1. Create bucket `spatialscan`; create an API token (Object Read & Write).
2. CORS on the bucket (browsers fetch `.splat` files directly):

```json
[
  {
    "AllowedOrigins": ["https://<your-pages-domain>"],
    "AllowedMethods": ["GET", "PUT"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```

3. API env:

```
STORAGE_BACKEND=s3
S3_BUCKET=spatialscan
S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
S3_REGION=auto
AWS_ACCESS_KEY_ID=<r2 key>
AWS_SECRET_ACCESS_KEY=<r2 secret>
```

Optional: lifecycle rule deleting `jobs/*/input.mp4` after 7 days (raw videos are only needed until processing completes).

## API (Fly.io example)

```bash
cd services/api
fly launch --dockerfile Dockerfile --name spatialscan-api
fly secrets set AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... RUNPOD_API_KEY=...
fly deploy
```

Env: the R2 block above, plus `JOB_TRIGGER=runpod`, `RUNPOD_ENDPOINT_ID=...`, `REDIS_URL=<upstash url>`, `CORS_ORIGINS=https://<pages-domain>`, `MAX_VIDEO_SECONDS=45`, `MAX_UPLOAD_MB=200`.

## Web (Cloudflare Pages)

- Build command: `npm ci && npm run build`, output `dist`, root `apps/web`.
- Set `VITE_API_BASE=https://<api-domain>` at build time (the app calls `${VITE_API_BASE}/api/...`).
- SPA routing: add a `_redirects` file or Pages "single-page app" mode so `/tour/*` and `/jobs/*` serve `index.html`.

## Checklist before first real user

- [ ] R2 CORS verified from the Pages domain (fetch a `.splat` in devtools)
- [ ] RunPod endpoint smoke-tested end-to-end (see endpoint.md)
- [ ] API `MAX_UPLOAD_MB` matches Fly request-size limits
- [ ] `CORS_ORIGINS` locked to the real domain (not `*`)
- [ ] Alerting on job error rate and GPU-seconds per job
