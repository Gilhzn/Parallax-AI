"""Read/write the antimatter15 ``.splat`` binary format.

Each splat is a fixed 32-byte record::

    offset  size  field
    0       12    position  (3 x float32, world units)
    12      12    scale     (3 x float32, per-axis gaussian extent)
    24      4     color     (4 x uint8, RGBA; A encodes opacity)
    28      4     rotation  (4 x uint8, quaternion wxyz mapped [-1,1] -> [0,255])

This layout is what ``@mkkellogg/gaussian-splats-3d`` (and the original
antimatter15 web viewer) load directly, so it is the single interchange
format between the training/export pipeline, the mock pipeline, tests,
and the web viewer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SPLAT_STRIDE = 32  # bytes per splat record


@dataclass
class SplatCloud:
    """A set of gaussians in unpacked, float form."""

    positions: np.ndarray  # (N, 3) float32
    scales: np.ndarray  # (N, 3) float32
    colors: np.ndarray  # (N, 4) uint8 RGBA
    rotations: np.ndarray  # (N, 4) float32 quaternion wxyz, unit norm

    def __post_init__(self) -> None:
        n = len(self.positions)
        for name, arr, width in (
            ("positions", self.positions, 3),
            ("scales", self.scales, 3),
            ("colors", self.colors, 4),
            ("rotations", self.rotations, 4),
        ):
            if arr.shape != (n, width):
                raise ValueError(f"{name} must have shape ({n}, {width}), got {arr.shape}")

    def __len__(self) -> int:
        return len(self.positions)


def write_splat(cloud: SplatCloud) -> bytes:
    """Pack a :class:`SplatCloud` into ``.splat`` bytes."""
    n = len(cloud)
    positions = np.ascontiguousarray(cloud.positions, dtype=np.float32)
    scales = np.ascontiguousarray(cloud.scales, dtype=np.float32)
    colors = np.clip(cloud.colors, 0, 255).astype(np.uint8)

    quats = cloud.rotations.astype(np.float32)
    norms = np.linalg.norm(quats, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    quats = quats / norms
    quats_u8 = np.clip(np.round(quats * 128.0 + 128.0), 0, 255).astype(np.uint8)

    buf = np.empty((n, SPLAT_STRIDE), dtype=np.uint8)
    buf[:, 0:12] = positions.view(np.uint8).reshape(n, 12)
    buf[:, 12:24] = scales.view(np.uint8).reshape(n, 12)
    buf[:, 24:28] = colors
    buf[:, 28:32] = quats_u8
    return buf.tobytes()


def read_splat(data: bytes) -> SplatCloud:
    """Unpack ``.splat`` bytes into a :class:`SplatCloud`.

    Rotations are returned dequantized to float32 (approximately unit norm).
    """
    if len(data) % SPLAT_STRIDE != 0:
        raise ValueError(f".splat byte length {len(data)} is not a multiple of {SPLAT_STRIDE}")
    n = len(data) // SPLAT_STRIDE
    buf = np.frombuffer(data, dtype=np.uint8).reshape(n, SPLAT_STRIDE)

    positions = buf[:, 0:12].copy().view(np.float32).reshape(n, 3)
    scales = buf[:, 12:24].copy().view(np.float32).reshape(n, 3)
    colors = buf[:, 24:28].copy()
    quats = (buf[:, 28:32].astype(np.float32) - 128.0) / 128.0
    return SplatCloud(positions=positions, scales=scales, colors=colors, rotations=quats)


def splat_count(data: bytes) -> int:
    if len(data) % SPLAT_STRIDE != 0:
        raise ValueError(f".splat byte length {len(data)} is not a multiple of {SPLAT_STRIDE}")
    return len(data) // SPLAT_STRIDE
