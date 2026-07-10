#!/usr/bin/env python3
"""REAL 3D Gaussian Splatting reconstruction on CPU — no GPU required.

Designed for the free GitHub Actions runners (see
.github/workflows/reconstruct.yml): ffmpeg frame extraction with blur
filtering -> COLMAP structure-from-motion (CPU SIFT) -> OpenSplat training
(libtorch CPU) -> web-ready .splat published into apps/web/public/tours/.

CPU training is ~100x slower than GPU, so this targets preview-grade
settings (downscaled frames, hundreds-to-thousands of iterations). It is
slow but it is REAL — the output is a reconstruction of the actual footage.
For maximum quality use the GPU paths (docs/QUALITY.md).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "services" / "worker"))

from spatialscan_worker.ply_io import ply_to_cloud  # noqa: E402
from spatialscan_worker.quality import laplacian_sharpness, select_sharpest  # noqa: E402
from spatialscan_worker.splat_format import write_splat  # noqa: E402
from spatialscan_worker.stages.export import prune_to_budget  # noqa: E402


def run(cmd: list[str], **kwargs) -> None:
    print(f"+ {' '.join(str(c) for c in cmd)}", flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kwargs)


def video_duration(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def extract_frames(video: Path, out_dir: Path, max_frames: int, downscale: int) -> int:
    """Extract downscaled candidates, keep the sharpest ones."""
    duration = video_duration(video)
    fps = min(max(max_frames * 1.6 / max(duration, 1.0), 0.5), 6.0)
    out_dir.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", video,
        "-vf", f"fps={fps:.3f},scale=iw/{downscale}:-2",
        "-q:v", "2", out_dir / "frame_%05d.jpg",
    ])
    candidates = sorted(out_dir.glob("frame_*.jpg"))
    if len(candidates) > max_frames:
        import numpy as np
        from PIL import Image

        def sharpness(p: Path) -> float:
            with Image.open(p) as img:
                img.thumbnail((480, 480))
                return laplacian_sharpness(np.asarray(img.convert("L"), dtype=np.float32))

        scores = [sharpness(p) for p in candidates]
        keep = set(select_sharpest(scores, max_frames))
        for i, p in enumerate(candidates):
            if i not in keep:
                p.unlink()
    kept = len(list(out_dir.glob("frame_*.jpg")))
    print(f"frames: kept {kept} of {len(candidates)} candidates ({duration:.1f}s video)")
    if kept < 8:
        raise SystemExit("too few frames extracted — is the video valid?")
    return kept


def run_colmap(images_dir: Path, work: Path) -> Path:
    """CPU structure-from-motion. Returns the project dir (images/ + sparse/0)."""
    db = work / "colmap.db"
    sparse = work / "sparse"
    sparse.mkdir(parents=True, exist_ok=True)
    run([
        "colmap", "feature_extractor",
        "--database_path", db, "--image_path", images_dir,
        "--ImageReader.camera_model", "SIMPLE_RADIAL",
        "--ImageReader.single_camera", "1",
        "--SiftExtraction.use_gpu", "0",
    ])
    run([
        "colmap", "sequential_matcher",
        "--database_path", db,
        "--SiftMatching.use_gpu", "0",
    ])
    run([
        "colmap", "mapper",
        "--database_path", db, "--image_path", images_dir,
        "--output_path", sparse,
    ])
    models = [d for d in sparse.iterdir() if (d / "images.bin").exists()]
    if not models:
        raise SystemExit(
            "COLMAP could not reconstruct camera poses. Film again with slow, "
            "sideways motion, good light and plenty of texture in view."
        )
    best = max(models, key=lambda d: (d / "images.bin").stat().st_size)
    print(f"colmap: using model {best.name} of {len(models)}")

    project = work / "project"
    (project / "sparse").mkdir(parents=True, exist_ok=True)
    shutil.copytree(images_dir, project / "images")
    shutil.copytree(best, project / "sparse" / "0")
    return project


def train_opensplat(opensplat: Path, project: Path, iterations: int, out_ply: Path) -> None:
    run([opensplat, project, "-n", iterations, "-o", out_ply], cwd=project)
    if not out_ply.exists():
        # some versions write into the project dir regardless of -o
        candidates = list(project.glob("*.ply")) + list(project.rglob("splat.ply"))
        if not candidates:
            raise SystemExit("opensplat finished but produced no .ply")
        shutil.copyfile(candidates[0], out_ply)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--video", type=Path, help="input video file")
    src.add_argument("--project", type=Path, help="existing COLMAP project (images/ + sparse/0)")
    ap.add_argument("--name", required=True, help="tour name (url-safe)")
    ap.add_argument("--iterations", type=int, default=800)
    ap.add_argument("--downscale", type=int, default=2)
    ap.add_argument("--max-frames", type=int, default=48)
    ap.add_argument("--max-mb", type=float, default=40.0)
    ap.add_argument("--opensplat", type=Path, required=True, help="path to opensplat binary")
    ap.add_argument("--out", type=Path, required=True, help="tours output directory")
    args = ap.parse_args()

    name = "".join(c if c.isalnum() or c in "-_" else "-" for c in args.name).strip("-") or "tour"
    work = Path("reconstruct-work")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    started = time.time()

    frame_count = None
    if args.video:
        frame_count = extract_frames(args.video, work / "frames", args.max_frames, args.downscale)
        project = run_colmap(work / "frames", work)
    else:
        project = args.project
        if not (project / "sparse").exists():
            # tolerate one level of nesting in downloaded sample archives
            nested = next((d for d in project.rglob("sparse") if d.is_dir()), None)
            if nested is None:
                raise SystemExit(f"no sparse/ reconstruction found under {project}")
            project = nested.parent
        print(f"using existing COLMAP project: {project}")

    out_ply = work / "scene.ply"
    train_opensplat(args.opensplat, project, args.iterations, out_ply)

    cloud = prune_to_budget(ply_to_cloud(out_ply), max_mb=args.max_mb)
    args.out.mkdir(parents=True, exist_ok=True)
    splat_path = args.out / f"{name}.splat"
    splat_path.write_bytes(write_splat(cloud))

    manifest = {
        "name": name,
        "splat_count": len(cloud),
        "size_bytes": splat_path.stat().st_size,
        "iterations": args.iterations,
        "frame_count": frame_count,
        "engine": "opensplat-cpu",
        "elapsed_sec": round(time.time() - started, 1),
    }
    (args.out / f"{name}.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    print(f"\ntour file: {splat_path}")


if __name__ == "__main__":
    main()
