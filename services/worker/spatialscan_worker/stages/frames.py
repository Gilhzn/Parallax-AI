"""Stage 1 — extract frames from the source video at ~FRAMES_PER_SECOND fps."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

from ..capabilities import has_ffmpeg, resolve_stage_mode

# A 1x1 valid JPEG so mock frames are real image files (keeps downstream
# tools that sniff magic bytes happy).
_TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000"
    "ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720"
    "222c231c1c2837292c30313434341f27393d38323c2e333432"
    "ffc0000b080001000101011100"
    "ffc4001f0000010501010101010100000000000000000102030405060708090a0b"
    "ffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1"
    "082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a5354"
    "55565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6"
    "a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3"
    "f4f5f6f7f8f9fa"
    "ffda0008010100003f00fb00"
    "ffd9"
)


def extract_frames(
    video_path: Path,
    out_dir: Path,
    fps: float,
    pipeline_mode: str,
    video_duration_sec: float | None = None,
) -> list[Path]:
    """Extract frames to ``out_dir`` and return their paths, sorted."""
    mode = resolve_stage_mode(pipeline_mode, has_ffmpeg(), "frames")
    out_dir.mkdir(parents=True, exist_ok=True)
    if mode == "real":
        _extract_real(video_path, out_dir, fps)
    else:
        _extract_mock(out_dir, fps, video_duration_sec)
    frames = sorted(out_dir.glob("frame_*.jpg"))
    if not frames:
        raise RuntimeError(f"frame extraction produced no frames in {out_dir}")
    return frames


def _extract_real(video_path: Path, out_dir: Path, fps: float) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps}",
        "-q:v",
        "2",
        str(out_dir / "frame_%05d.jpg"),
    ]
    subprocess.run(cmd, check=True)


def _extract_mock(out_dir: Path, fps: float, video_duration_sec: float | None) -> None:
    duration = video_duration_sec if video_duration_sec else 10.0
    count = max(4, math.ceil(duration * fps))
    for i in range(1, count + 1):
        (out_dir / f"frame_{i:05d}.jpg").write_bytes(_TINY_JPEG)
