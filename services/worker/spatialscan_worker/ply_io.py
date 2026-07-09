"""Convert a 3D Gaussian Splatting PLY (as exported by nerfstudio / the
original INRIA implementation) into a :class:`SplatCloud`.

The PLY carries raw optimizer parameters; standard 3DGS conventions apply:
color = 0.5 + SH_C0 * f_dc, opacity = sigmoid(opacity), scale = exp(scale).
Only ``binary_little_endian`` PLYs with float32 properties are supported —
that is what every 3DGS exporter emits.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .splat_format import SplatCloud

SH_C0 = 0.28209479177387814


def _parse_header(data: bytes) -> tuple[int, list[str], int]:
    """Return (vertex_count, property_names, header_byte_length)."""
    end = data.find(b"end_header\n")
    if end < 0:
        raise ValueError("not a PLY file (no end_header)")
    header_len = end + len(b"end_header\n")
    lines = data[:end].decode("ascii", errors="replace").splitlines()
    if not lines or lines[0].strip() != "ply":
        raise ValueError("not a PLY file (missing magic)")

    count = 0
    props: list[str] = []
    in_vertex = False
    for line in lines[1:]:
        parts = line.strip().split()
        if not parts:
            continue
        if parts[0] == "format" and parts[1] != "binary_little_endian":
            raise ValueError(f"unsupported PLY format {parts[1]}")
        if parts[0] == "element":
            in_vertex = parts[1] == "vertex"
            if in_vertex:
                count = int(parts[2])
        elif parts[0] == "property" and in_vertex:
            if parts[1] != "float":
                raise ValueError(f"unsupported vertex property type {parts[1]}")
            props.append(parts[2])
    if count == 0 or not props:
        raise ValueError("PLY has no vertex element")
    return count, props, header_len


def ply_to_cloud(path: Path) -> SplatCloud:
    data = path.read_bytes()
    count, props, header_len = _parse_header(data)
    idx = {name: i for i, name in enumerate(props)}
    for required in ("x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity",
                     "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"):
        if required not in idx:
            raise ValueError(f"PLY missing 3DGS property '{required}'")

    table = np.frombuffer(
        data, dtype=np.float32, count=count * len(props), offset=header_len
    ).reshape(count, len(props))

    positions = table[:, [idx["x"], idx["y"], idx["z"]]].astype(np.float32)
    scales = np.exp(table[:, [idx["scale_0"], idx["scale_1"], idx["scale_2"]]]).astype(np.float32)
    rotations = table[:, [idx["rot_0"], idx["rot_1"], idx["rot_2"], idx["rot_3"]]].astype(
        np.float32
    )

    rgb = np.clip(
        (0.5 + SH_C0 * table[:, [idx["f_dc_0"], idx["f_dc_1"], idx["f_dc_2"]]]) * 255.0, 0, 255
    )
    alpha = np.clip(1.0 / (1.0 + np.exp(-table[:, idx["opacity"]])) * 255.0, 0, 255)
    colors = np.concatenate([rgb, alpha[:, None]], axis=1).astype(np.uint8)

    return SplatCloud(positions=positions, scales=scales, colors=colors, rotations=rotations)
