"""Probe which real pipeline tools are available on this machine.

``PIPELINE_MODE=auto`` uses these to decide, per stage, whether to run the
real implementation or fall back to the mock one.
"""

from __future__ import annotations

import shutil


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def has_colmap() -> bool:
    # ns-process-data drives COLMAP; either binary present counts.
    return shutil.which("colmap") is not None or shutil.which("ns-process-data") is not None


def has_nerfstudio() -> bool:
    return shutil.which("ns-train") is not None


def has_cuda() -> bool:
    try:
        import torch  # noqa: PLC0415

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def resolve_stage_mode(pipeline_mode: str, stage_available: bool, stage: str) -> str:
    """Return 'real' or 'mock' for one stage given the global pipeline mode."""
    if pipeline_mode == "mock":
        return "mock"
    if pipeline_mode == "real":
        if not stage_available:
            raise RuntimeError(
                f"PIPELINE_MODE=real but the tools for stage '{stage}' are not installed. "
                "Run inside the GPU Docker image or Colab (see docs/FREE_TIER_TESTING.md), "
                "or use PIPELINE_MODE=auto/mock."
            )
        return "real"
    if pipeline_mode == "auto":
        return "real" if stage_available else "mock"
    raise ValueError(f"unknown PIPELINE_MODE '{pipeline_mode}' (expected mock|auto|real)")
