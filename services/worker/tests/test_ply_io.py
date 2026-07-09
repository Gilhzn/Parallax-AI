import numpy as np
import pytest

from spatialscan_worker.ply_io import SH_C0, ply_to_cloud


def _write_3dgs_ply(path, n=16, seed=5):
    rng = np.random.default_rng(seed)
    props = [
        "x", "y", "z",
        "f_dc_0", "f_dc_1", "f_dc_2",
        "opacity",
        "scale_0", "scale_1", "scale_2",
        "rot_0", "rot_1", "rot_2", "rot_3",
    ]
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {n}\n"
        + "".join(f"property float {p}\n" for p in props)
        + "end_header\n"
    )
    table = rng.normal(0, 1, (n, len(props))).astype(np.float32)
    path.write_bytes(header.encode("ascii") + table.tobytes())
    return table, props


def test_ply_conversion(tmp_path):
    path = tmp_path / "splat.ply"
    table, props = _write_3dgs_ply(path)
    cloud = ply_to_cloud(path)

    assert len(cloud) == len(table)
    np.testing.assert_array_equal(cloud.positions, table[:, 0:3])
    # scale = exp(raw), color = (0.5 + C0 * f_dc) * 255, alpha = sigmoid * 255
    np.testing.assert_allclose(cloud.scales, np.exp(table[:, 7:10]), rtol=1e-6)
    expected_rgb = np.clip((0.5 + SH_C0 * table[:, 3:6]) * 255, 0, 255).astype(np.uint8)
    np.testing.assert_array_equal(cloud.colors[:, :3], expected_rgb)
    expected_alpha = np.clip(1 / (1 + np.exp(-table[:, 6])) * 255, 0, 255).astype(np.uint8)
    np.testing.assert_array_equal(cloud.colors[:, 3], expected_alpha)


def test_rejects_non_ply(tmp_path):
    path = tmp_path / "junk.ply"
    path.write_bytes(b"not a ply at all")
    with pytest.raises(ValueError):
        ply_to_cloud(path)


def test_rejects_missing_3dgs_props(tmp_path):
    path = tmp_path / "plain.ply"
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        "element vertex 1\n"
        "property float x\nproperty float y\nproperty float z\n"
        "end_header\n"
    )
    path.write_bytes(header.encode() + np.zeros(3, np.float32).tobytes())
    with pytest.raises(ValueError, match="f_dc_0"):
        ply_to_cloud(path)
