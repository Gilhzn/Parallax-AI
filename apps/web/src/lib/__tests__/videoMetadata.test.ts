import { describe, expect, it } from 'vitest';

import { checkDuration, estimateFps, MAX_VIDEO_SECONDS } from '../videoMetadata';

describe('checkDuration', () => {
  it('accepts videos within the limit', () => {
    expect(checkDuration(10).ok).toBe(true);
    expect(checkDuration(MAX_VIDEO_SECONDS).ok).toBe(true);
  });

  it('rejects videos over the limit with a helpful message', () => {
    const result = checkDuration(90);
    expect(result.ok).toBe(false);
    expect(result.error).toContain('90s');
    expect(result.error).toContain(`${MAX_VIDEO_SECONDS}s`);
  });

  it('rejects unreadable durations (NaN / Infinity / 0)', () => {
    expect(checkDuration(NaN).ok).toBe(false);
    expect(checkDuration(Infinity).ok).toBe(false);
    expect(checkDuration(0).ok).toBe(false);
  });
});

describe('estimateFps', () => {
  it('estimates 30fps from evenly spaced frame times', () => {
    const times = Array.from({ length: 10 }, (_, i) => i / 30);
    expect(estimateFps(times)).toBeCloseTo(30, 0);
  });

  it('estimates 60fps', () => {
    const times = Array.from({ length: 10 }, (_, i) => i / 60);
    expect(estimateFps(times)).toBeCloseTo(60, 0);
  });

  it('returns null with too few samples', () => {
    expect(estimateFps([])).toBeNull();
    expect(estimateFps([0.5])).toBeNull();
  });

  it('returns null for degenerate timestamps', () => {
    expect(estimateFps([1, 1, 1])).toBeNull();
  });

  it('tolerates jitter', () => {
    const times = [0, 0.034, 0.066, 0.101, 0.133, 0.168];
    const fps = estimateFps(times);
    expect(fps).not.toBeNull();
    expect(fps!).toBeGreaterThan(25);
    expect(fps!).toBeLessThan(35);
  });
});
