"""Quality presets — the dials that decide how faithful the reconstruction is.

Reconstruction quality is bought with three currencies: input frames (more,
sharper, full resolution), optimization work (iterations, model capacity),
and output budget (how many gaussians survive export). A preset fixes all
three coherently:

| preset   | frames                | training                     | export      |
|----------|-----------------------|------------------------------|-------------|
| fast     | 2 fps, all kept       | splatfacto, 7k iters         | 25 MB       |
| balanced | 3 fps, all kept       | splatfacto, 15k iters, SH3   | 40 MB       |
| high     | 6 fps candidates,     | splatfacto-big, 30k iters,   | 150 MB      |
|          | sharpest ~55% kept,   | SH3, full input resolution   | + raw PLY   |
|          | full resolution       |                              |             |

"high" is the no-compromise mode: nothing is downscaled, blurry frames are
discarded instead of poisoning COLMAP and training, and the raw PLY (with
full spherical harmonics) is kept alongside the web-ready .splat.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityPreset:
    name: str
    fps: float  # candidate frame extraction rate
    keep_ratio: float  # fraction of sharpest candidates kept (1.0 = keep all)
    max_frames: int  # hard cap so COLMAP stays tractable
    train_iterations: int
    model: str  # nerfstudio method: splatfacto | splatfacto-big
    sh_degree: int  # spherical-harmonics degree (view-dependent color)
    full_resolution: bool  # forbid training-time downscaling
    splat_max_mb: float
    keep_ply: bool  # archive the lossless PLY next to the .splat


PRESETS: dict[str, QualityPreset] = {
    "fast": QualityPreset(
        name="fast", fps=2.0, keep_ratio=1.0, max_frames=60,
        train_iterations=7000, model="splatfacto", sh_degree=2,
        full_resolution=False, splat_max_mb=25.0, keep_ply=False,
    ),
    "balanced": QualityPreset(
        name="balanced", fps=3.0, keep_ratio=1.0, max_frames=140,
        train_iterations=15000, model="splatfacto", sh_degree=3,
        full_resolution=False, splat_max_mb=40.0, keep_ply=False,
    ),
    "high": QualityPreset(
        name="high", fps=6.0, keep_ratio=0.55, max_frames=240,
        train_iterations=30000, model="splatfacto-big", sh_degree=3,
        full_resolution=True, splat_max_mb=150.0, keep_ply=True,
    ),
}


def get_preset(name: str) -> QualityPreset:
    try:
        return PRESETS[name]
    except KeyError:
        raise ValueError(
            f"unknown quality preset '{name}' (expected one of {sorted(PRESETS)})"
        ) from None


def laplacian_sharpness(gray: "np.ndarray") -> float:  # noqa: F821 (doc type)
    """Variance of the Laplacian — the standard focus/blur metric.

    ``gray`` is a 2D float array. Higher = sharper. Comparable only between
    frames of the same video (absolute value depends on content).
    """
    import numpy as np

    lap = (
        -4.0 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
    )
    return float(np.var(lap))


def select_sharpest(sharpness: list[float], keep: int) -> list[int]:
    """Pick ``keep`` frame indices, preferring sharp frames while preserving
    temporal coverage.

    The naive global top-K clusters around the steadiest second of footage
    and starves COLMAP elsewhere, so instead the sequence is split into
    ``keep`` equal windows and the sharpest frame of each window wins.
    Returned indices are sorted (temporal order).
    """
    n = len(sharpness)
    if keep >= n:
        return list(range(n))
    if keep <= 0:
        return []
    picked = []
    for w in range(keep):
        lo = round(w * n / keep)
        hi = max(round((w + 1) * n / keep), lo + 1)
        window = range(lo, min(hi, n))
        picked.append(max(window, key=lambda i: sharpness[i]))
    return sorted(set(picked))
