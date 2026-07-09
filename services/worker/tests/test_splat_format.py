import numpy as np
import pytest

from spatialscan_worker.splat_format import (
    SPLAT_STRIDE,
    SplatCloud,
    read_splat,
    splat_count,
    write_splat,
)
from spatialscan_worker.synthetic import synthetic_room_splats


def _tiny_cloud(n: int = 8) -> SplatCloud:
    rng = np.random.default_rng(1)
    return SplatCloud(
        positions=rng.normal(0, 1, (n, 3)).astype(np.float32),
        scales=rng.random((n, 3)).astype(np.float32),
        colors=rng.integers(0, 256, (n, 4)).astype(np.uint8),
        rotations=rng.normal(0, 1, (n, 4)).astype(np.float32),
    )


def test_byte_layout():
    cloud = _tiny_cloud(10)
    data = write_splat(cloud)
    assert len(data) == 10 * SPLAT_STRIDE
    assert splat_count(data) == 10


def test_round_trip_positions_scales_colors():
    cloud = _tiny_cloud(64)
    back = read_splat(write_splat(cloud))
    np.testing.assert_array_equal(back.positions, cloud.positions)
    np.testing.assert_array_equal(back.scales, cloud.scales)
    np.testing.assert_array_equal(back.colors, cloud.colors)


def test_rotations_normalized_and_quantized():
    cloud = _tiny_cloud(64)
    back = read_splat(write_splat(cloud))
    # Dequantized quaternions should be unit norm within quantization error.
    norms = np.linalg.norm(back.rotations, axis=1)
    assert np.all(np.abs(norms - 1.0) < 0.02)


def test_invalid_length_rejected():
    with pytest.raises(ValueError):
        read_splat(b"\x00" * (SPLAT_STRIDE + 1))


def test_shape_mismatch_rejected():
    cloud = _tiny_cloud(4)
    with pytest.raises(ValueError):
        SplatCloud(
            positions=cloud.positions,
            scales=cloud.scales[:2],
            colors=cloud.colors,
            rotations=cloud.rotations,
        )


def test_synthetic_room_is_deterministic_and_valid():
    a = synthetic_room_splats(total=1000, seed=7)
    b = synthetic_room_splats(total=1000, seed=7)
    np.testing.assert_array_equal(a.positions, b.positions)
    data = write_splat(a)
    assert splat_count(data) == len(a)
    # Room geometry sanity: floor near y=0, nothing above the ceiling.
    assert a.positions[:, 1].min() > -0.2
    assert a.positions[:, 1].max() < 3.0
