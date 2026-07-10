# captures/ — drop a video here to reconstruct it for free

Upload a video file (`.mp4` / `.mov` / `.webm`, ≤45s recommended) into this
folder — on GitHub: **Add file → Upload files** — and the
[Reconstruct workflow](../.github/workflows/reconstruct.yml) will run REAL
structure-from-motion + Gaussian Splatting training on GitHub's free CPU
runners and publish the result to the live site at
`https://gilhzn.github.io/Parallax-AI/tour/<filename>`.

Alternatively, run the workflow manually from the **Actions** tab with a
direct video URL (no file committed to the repo that way — better for large
videos, since files uploaded here stay in git history).

Optional `request.json` here can set parameters for URL-based runs:

```json
{ "source": "https://example.com/my-room.mp4", "name": "my-room", "iterations": 1500, "downscale": 2, "max_frames": 48 }
```

Expect 1–3 hours per run (CPU training is ~100x slower than GPU) and
preview-grade quality. For maximum quality see [docs/QUALITY.md](../docs/QUALITY.md).

עברית: העלה לכאן קובץ וידאו (דרך Add file → Upload files) — ותוך שעה-שלוש
יהיה סיור תלת-ממדי **אמיתי** של מה שצילמת באתר, בחינם, בלי שום חשבון נוסף.
צלם לאט, בתנועה הצידה, עם הרבה אור.
