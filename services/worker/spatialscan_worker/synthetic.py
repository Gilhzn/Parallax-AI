"""Procedural synthetic room used by the mock pipeline, tests, and the demo asset.

Generates a recognizable indoor scene (floor, four walls, a few furniture
blobs) as a :class:`~spatialscan_worker.splat_format.SplatCloud`. Deterministic
for a given seed so mock pipeline output and the committed sample asset are
reproducible.

Coordinate system matches the web viewer: +Y up, floor at y=0, room centered
on the origin. Room is 6m x 6m with 2.6m ceilings.
"""

from __future__ import annotations

import numpy as np

from .splat_format import SplatCloud

ROOM_HALF = 3.0  # half-width of the room in meters
WALL_HEIGHT = 2.6

# RGB palette (0-255)
_FLOOR = (168, 136, 98)  # warm wood
_WALLS = [
    (214, 208, 196),  # north - off-white
    (196, 184, 168),  # south - beige
    (170, 190, 200),  # east  - pale blue
    (206, 176, 160),  # west  - blush
]
_FURNITURE = [
    # (center xz, size xyz, color)
    ((-1.6, -1.4), (1.6, 0.45, 0.8), (90, 105, 140)),  # sofa - navy
    ((1.5, 1.2), (0.9, 0.75, 0.9), (120, 84, 60)),  # table - brown
    ((0.2, -2.4), (0.5, 1.7, 0.5), (60, 120, 80)),  # plant - green
    ((2.4, -1.8), (0.8, 1.1, 0.4), (150, 150, 155)),  # shelf - grey
]


def _plane(
    rng: np.random.Generator,
    n: int,
    origin: tuple[float, float, float],
    u_axis: tuple[float, float, float],
    v_axis: tuple[float, float, float],
    color: tuple[int, int, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample n gaussians on a rectangle origin + s*u + t*v, s,t in [0,1]."""
    origin_v = np.asarray(origin, dtype=np.float32)
    u = np.asarray(u_axis, dtype=np.float32)
    v = np.asarray(v_axis, dtype=np.float32)
    s = rng.random((n, 1), dtype=np.float32)
    t = rng.random((n, 1), dtype=np.float32)
    pos = origin_v + s * u + t * v
    pos += rng.normal(0, 0.008, pos.shape).astype(np.float32)

    # Flat disc-like gaussians: thin along the plane normal.
    normal = np.cross(u, v)
    normal /= np.linalg.norm(normal)
    in_plane = 0.09 + rng.random((n, 1), dtype=np.float32) * 0.05
    thin = np.full((n, 1), 0.015, dtype=np.float32)
    scale = in_plane * (1.0 - np.abs(normal)) + thin * np.abs(normal)

    shade = rng.normal(1.0, 0.05, (n, 1))
    rgb = np.clip(np.asarray(color, dtype=np.float32) * shade, 0, 255)
    colors = np.concatenate([rgb, np.full((n, 1), 255.0)], axis=1)
    return pos.astype(np.float32), scale.astype(np.float32), colors.astype(np.uint8)


def _blob(
    rng: np.random.Generator,
    n: int,
    center_xz: tuple[float, float],
    size: tuple[float, float, float],
    color: tuple[int, int, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample n gaussians on the surface of a box sitting on the floor."""
    cx, cz = center_xz
    sx, sy, sz = size
    # Sample points on box faces by clamping uniform interior points outward.
    p = rng.random((n, 3), dtype=np.float32) * 2.0 - 1.0  # [-1,1]^3
    axis = rng.integers(0, 3, n)
    sign = rng.choice([-1.0, 1.0], n).astype(np.float32)
    p[np.arange(n), axis] = sign
    pos = np.stack(
        [
            cx + p[:, 0] * sx / 2,
            (p[:, 1] * 0.5 + 0.5) * sy,  # from floor up
            cz + p[:, 2] * sz / 2,
        ],
        axis=1,
    ).astype(np.float32)

    scale = (0.04 + rng.random((n, 3), dtype=np.float32) * 0.05).astype(np.float32)
    shade = rng.normal(1.0, 0.08, (n, 1))
    rgb = np.clip(np.asarray(color, dtype=np.float32) * shade, 0, 255)
    colors = np.concatenate([rgb, np.full((n, 1), 255.0)], axis=1)
    return pos, scale, colors.astype(np.uint8)


def synthetic_room_splats(total: int = 5000, seed: int = 42) -> SplatCloud:
    """Build the synthetic room as a splat cloud of roughly ``total`` gaussians."""
    rng = np.random.default_rng(seed)
    h = ROOM_HALF

    n_floor = int(total * 0.30)
    n_wall = int(total * 0.11)  # per wall
    n_furniture = max(1, (total - n_floor - 4 * n_wall) // len(_FURNITURE))

    parts = [
        # Floor: y=0 plane spanning the room.
        _plane(rng, n_floor, (-h, 0.0, -h), (2 * h, 0, 0), (0, 0, 2 * h), _FLOOR),
        # Walls (normal facing inward is irrelevant for splats).
        _plane(rng, n_wall, (-h, 0.0, -h), (2 * h, 0, 0), (0, WALL_HEIGHT, 0), _WALLS[0]),
        _plane(rng, n_wall, (-h, 0.0, h), (2 * h, 0, 0), (0, WALL_HEIGHT, 0), _WALLS[1]),
        _plane(rng, n_wall, (h, 0.0, -h), (0, 0, 2 * h), (0, WALL_HEIGHT, 0), _WALLS[2]),
        _plane(rng, n_wall, (-h, 0.0, -h), (0, 0, 2 * h), (0, WALL_HEIGHT, 0), _WALLS[3]),
    ]
    for center, size, color in _FURNITURE:
        parts.append(_blob(rng, n_furniture, center, size, color))

    positions = np.concatenate([p[0] for p in parts])
    scales = np.concatenate([p[1] for p in parts])
    colors = np.concatenate([p[2] for p in parts])

    n = len(positions)
    # Mild random orientations around identity keep the scene stable but organic.
    rotations = np.concatenate(
        [
            np.ones((n, 1), dtype=np.float32),
            rng.normal(0, 0.08, (n, 3)).astype(np.float32),
        ],
        axis=1,
    )
    return SplatCloud(positions=positions, scales=scales, colors=colors, rotations=rotations)
