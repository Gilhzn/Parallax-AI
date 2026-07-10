import numpy as np
import pytest

from spatialscan_worker.pipeline import JobSpec
from spatialscan_worker.quality import (
    PRESETS,
    get_preset,
    laplacian_sharpness,
    select_sharpest,
)


def test_presets_are_coherent():
    assert set(PRESETS) == {"fast", "balanced", "high"}
    high, balanced, fast = PRESETS["high"], PRESETS["balanced"], PRESETS["fast"]
    # "high" must dominate on every quality axis
    assert high.train_iterations > balanced.train_iterations > fast.train_iterations
    assert high.fps > balanced.fps
    assert high.splat_max_mb > balanced.splat_max_mb
    assert high.full_resolution and high.keep_ply
    assert high.model == "splatfacto-big"
    assert high.sh_degree == 3


def test_unknown_preset_rejected():
    with pytest.raises(ValueError, match="unknown quality preset"):
        get_preset("ultra")


def test_laplacian_separates_sharp_from_blurry():
    rng = np.random.default_rng(0)
    sharp = rng.uniform(0, 255, (120, 120)).astype(np.float32)  # high-frequency noise
    blurry = np.full((120, 120), 128.0, np.float32)  # flat = no detail
    # box-blur the sharp image a few times -> intermediate
    smoothed = sharp.copy()
    for _ in range(8):
        smoothed = (
            smoothed
            + np.roll(smoothed, 1, 0)
            + np.roll(smoothed, -1, 0)
            + np.roll(smoothed, 1, 1)
            + np.roll(smoothed, -1, 1)
        ) / 5.0
    assert laplacian_sharpness(sharp) > laplacian_sharpness(smoothed) > laplacian_sharpness(blurry)


def test_select_sharpest_prefers_sharp_but_keeps_coverage():
    # 20 frames, frame 3 and 17 are tack sharp, frames 8-11 are blurry
    sharpness = [5.0] * 20
    sharpness[3] = 50.0
    sharpness[17] = 40.0
    for i in range(8, 12):
        sharpness[i] = 0.5
    picked = select_sharpest(sharpness, keep=5)
    assert len(picked) == 5
    assert picked == sorted(picked)
    assert 3 in picked and 17 in picked
    # windowed selection keeps temporal coverage: something from each fifth
    for w in range(5):
        assert any(w * 4 <= i < (w + 1) * 4 for i in picked)


def test_select_sharpest_edge_cases():
    assert select_sharpest([1.0, 2.0], keep=5) == [0, 1]
    assert select_sharpest([1.0, 2.0, 3.0], keep=0) == []


def test_jobspec_resolves_preset_with_overrides(tmp_path):
    spec = JobSpec(
        job_id="q1", video_path=tmp_path / "v.mp4", output_dir=tmp_path,
        quality="high", train_iterations=12345,
    )
    preset = spec.resolved_preset()
    assert preset.name == "high"
    assert preset.train_iterations == 12345  # explicit override wins
    assert preset.full_resolution is True
    assert preset.keep_ply is True

    default = JobSpec(job_id="q2", video_path=tmp_path / "v.mp4", output_dir=tmp_path)
    assert default.resolved_preset().name == "balanced"
