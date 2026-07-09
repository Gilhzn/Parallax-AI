#!/usr/bin/env python3
"""Regenerate the committed demo scene at apps/web/public/sample.splat."""

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "services" / "worker"))

from spatialscan_worker.splat_format import write_splat  # noqa: E402
from spatialscan_worker.synthetic import synthetic_room_splats  # noqa: E402


def main() -> None:
    cloud = synthetic_room_splats(total=5000, seed=42)
    data = write_splat(cloud)
    out = REPO_ROOT / "apps" / "web" / "public" / "sample.splat"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"wrote {out} ({len(cloud)} splats, {len(data) / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
