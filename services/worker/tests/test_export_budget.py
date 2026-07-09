import numpy as np

from spatialscan_worker.splat_format import SPLAT_STRIDE, SplatCloud
from spatialscan_worker.stages.export import export_splat, prune_to_budget


def _cloud(n: int, seed: int = 3) -> SplatCloud:
    rng = np.random.default_rng(seed)
    return SplatCloud(
        positions=rng.normal(0, 1, (n, 3)).astype(np.float32),
        scales=rng.random((n, 3)).astype(np.float32),
        colors=rng.integers(0, 256, (n, 4)).astype(np.uint8),
        rotations=rng.normal(0, 1, (n, 4)).astype(np.float32),
    )


def test_under_budget_untouched():
    cloud = _cloud(1000)
    assert prune_to_budget(cloud, max_mb=1.0) is cloud


def test_oversized_cloud_pruned_to_fit(tmp_path):
    budget_mb = 0.01  # 10 KiB -> 327 splats
    cloud = _cloud(5000)
    out = export_splat(cloud, tmp_path / "scene.splat", max_mb=budget_mb)
    size = out.stat().st_size
    assert size <= budget_mb * 1024 * 1024
    assert size % SPLAT_STRIDE == 0
    assert size // SPLAT_STRIDE == int(budget_mb * 1024 * 1024) // SPLAT_STRIDE


def test_pruning_keeps_most_significant():
    n = 100
    cloud = _cloud(n)
    # Make splat 7 maximally significant and splat 8 fully transparent.
    cloud.colors[:, 3] = 128
    cloud.colors[7, 3] = 255
    cloud.scales[7, :] = 1.0
    cloud.colors[8, 3] = 0
    max_mb = (50 * SPLAT_STRIDE) / (1024 * 1024)  # keep 50 of 100
    pruned = prune_to_budget(cloud, max_mb=max_mb)
    assert len(pruned) == 50
    kept_positions = {tuple(p) for p in pruned.positions.tolist()}
    assert tuple(cloud.positions[7].tolist()) in kept_positions
    assert tuple(cloud.positions[8].tolist()) not in kept_positions
