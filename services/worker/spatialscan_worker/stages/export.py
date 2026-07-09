"""Stage 4 — export the trained gaussians as a size-budgeted ``.splat`` file.

Always runs "for real" (pure numpy). If the cloud exceeds the byte budget,
the least significant splats are pruned first: primary key opacity (alpha),
secondary key footprint (mean scale) — a transparent, tiny splat contributes
least to the rendered image.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..splat_format import SPLAT_STRIDE, SplatCloud, write_splat


def prune_to_budget(cloud: SplatCloud, max_mb: float) -> SplatCloud:
    max_splats = int(max_mb * 1024 * 1024) // SPLAT_STRIDE
    if len(cloud) <= max_splats:
        return cloud
    alpha = cloud.colors[:, 3].astype(np.float32) / 255.0
    footprint = cloud.scales.mean(axis=1)
    significance = alpha * footprint
    keep = np.argsort(significance)[::-1][:max_splats]
    keep.sort()  # preserve original ordering for deterministic output
    return SplatCloud(
        positions=cloud.positions[keep],
        scales=cloud.scales[keep],
        colors=cloud.colors[keep],
        rotations=cloud.rotations[keep],
    )


def export_splat(cloud: SplatCloud, out_path: Path, max_mb: float) -> Path:
    pruned = prune_to_budget(cloud, max_mb)
    data = write_splat(pruned)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return out_path
