# Reconstruction Quality Guide · מדריך איכות השחזור

How to get a reconstruction that is faithful to the video you filmed — and what actually controls quality at every stage.

איך מקבלים שחזור נאמן לסרטון שצילמת — ומה באמת שולט באיכות בכל שלב.

---

## The presets · הפריסטים

Select in the app's upload screen, or via CLI `--quality`, or env `QUALITY_PRESET`.

| | `fast` | `balanced` | **`high` (מקסימום)** |
|---|---|---|---|
| Frame candidates | 2 fps | 3 fps | **6 fps** |
| Blur filtering | – | – | **keeps sharpest ~55% (variance-of-Laplacian, windowed for temporal coverage)** |
| Max frames | 60 | 140 | **240** |
| Input resolution | auto-downscaled | auto-downscaled | **original pixels — no downscaling anywhere** |
| Model | splatfacto | splatfacto | **splatfacto-big** |
| Iterations | 7,000 | 15,000 | **30,000** |
| View-dependent color (SH) | degree 2 | degree 3 | **degree 3** |
| Export budget | 25 MB | 40 MB | **150 MB** |
| Lossless archive | – | – | **scene.ply kept (full spherical harmonics)** |
| Time on T4 (free Colab) | ~3–5 min | ~10–20 min | ~45–90 min |
| Time on RTX 4090 | ~1 min | ~3–5 min | **~10–20 min** |
| Cost on RunPod 4090 | <$0.02 | ~$0.05 | **~$0.15–0.25** |

Per-field overrides: `--fps`, `--iterations`, `--max-mb` (CLI) or `FRAMES_PER_SECOND`, `TRAIN_ITERATIONS`, `SPLAT_MAX_MB` (env) — they win over the preset.

## What each stage does for quality · מה כל שלב תורם

1. **Frames** — quality is decided here first. `high` extracts 6 candidates/second at full resolution (`-q:v 1` JPEG), scores each with the variance-of-Laplacian focus metric, and keeps only the sharpest frame per time-window. Motion-blurred frames don't just look bad — they corrupt COLMAP's feature matching and smear the trained gaussians.
2. **Poses (COLMAP)** — sequential matching (frames are temporally ordered) registers more frames more reliably than exhaustive matching on video footage.
3. **Training** — `splatfacto-big` densifies to far more gaussians; 30k iterations lets fine texture converge; SH degree 3 captures reflections/highlights that change with viewing angle; `--downscale-factor 1` forbids nerfstudio's automatic image downscaling.
4. **Export** — the web `.splat` format quantizes color to RGBA (view-independent). That is a real quality loss, so `high` also keeps **`scene.ply`** — the full lossless model — for archival, re-export, or desktop viewers ([SuperSplat](https://playcanvas.com/supersplat/editor), Blender's 3DGS add-ons). The `.splat` budget (150 MB) keeps essentially all gaussians for typical rooms; pruning only trims near-invisible ones (lowest opacity × footprint).

## Filming for maximum quality · צילום נכון = רוב האיכות

The single biggest quality factor is the capture itself:

- **תזוזה, לא סיבוב:** ללכת הצידה ובקשת סביב החדר — parallax הוא המידע התלת-ממדי. סיבוב במקום = אפס מידע עומק.
- **לאט וחלק:** תנועה מהירה = motion blur. ב-45 שניות עדיף לכסות פחות שטח לאט מאשר הכל מהר.
- **חפיפה:** כל פינה צריכה להופיע בכמה שניות של וידאו מזוויות שונות.
- **אור:** תאורה חזקה ואחידה; ISO גבוה = רעש שהמודל ילמד.
- **להימנע מ:** משטחים חלקים בלי טקסטורה, מראות וזכוכית גדולה, אנשים/חיות זזים.
- **הגדרות מצלמה:** 4K אם אפשר, 30fps, נעילת חשיפה/פוקוס אם המצלמה מאפשרת.

## Where to run `high` · איפה מריצים

| Where | How | Notes |
|---|---|---|
| **Free — Google Colab T4** | notebook: [`notebooks/spatialscan_worker_colab.ipynb`](../notebooks/spatialscan_worker_colab.ipynb), set `QUALITY='high'` | 45–90 min; free tier may disconnect — `balanced` is the safe default there |
| **Colab Pro (A100)** | same notebook | `high` in ~10–15 min |
| **RunPod pod (interactive)** | worker Docker image + `python -m spatialscan_worker.cli --quality high` | 4090 ≈ $0.35/hr billed per second |
| **Production (serverless)** | app upload screen → "Maximum" | requires the RunPod endpoint from [infra/runpod/endpoint.md](../infra/runpod/endpoint.md); set execution timeout ≥ 3600s for `high` |

⚠️ **The GitHub Pages demo cannot reconstruct** — it has no GPU behind it; it always shows the built-in sample scene (clearly labeled "Demo mode"). Real reconstructions of your videos come only from the paths above.

## Quality checklist for a finished tour · בדיקת תוצאה

- COLMAP registered >85% of frames (printed in the pipeline log) — lower means the footage needs re-filming.
- No large "floaters" between the camera path and the room.
- Text/edges readable at walking distance.
- `manifest.json` records the preset, model, iterations and whether full resolution was used — every tour is reproducible.
