import { describe, expect, it } from 'vitest';

import { sanitizeTourName } from './client';

describe('sanitizeTourName', () => {
  it('lowercases and strips extension', () => {
    expect(sanitizeTourName('MyRoom.MP4')).toBe('myroom');
  });

  it('replaces unsafe characters (including Hebrew) with dashes', () => {
    expect(sanitizeTourName('סלון בבית.mov')).toBe('tour'); // fully non-latin -> fallback
    expect(sanitizeTourName('living room (v2)!.mp4')).toBe('living-room-v2');
  });

  it('trims and caps length', () => {
    expect(sanitizeTourName('---x---.mp4')).toBe('x');
    expect(sanitizeTourName(`${'a'.repeat(80)}.mp4`).length).toBeLessThanOrEqual(40);
  });

  it('falls back for empty results', () => {
    expect(sanitizeTourName('....mp4')).toBe('tour');
  });
});
