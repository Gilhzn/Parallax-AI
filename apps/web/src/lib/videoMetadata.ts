import type { VideoMetadata } from '../api/client';

export const MAX_VIDEO_SECONDS = 45;

/** Pure duration guardrail — mirrors the server-side check. */
export function checkDuration(
  durationSec: number,
  maxSeconds: number = MAX_VIDEO_SECONDS,
): { ok: boolean; error?: string } {
  if (!Number.isFinite(durationSec) || durationSec <= 0) {
    return { ok: false, error: 'Could not read the video duration.' };
  }
  if (durationSec > maxSeconds) {
    return {
      ok: false,
      error: `Video is ${Math.round(durationSec)}s — the MVP limit is ${maxSeconds}s. Trim it and try again.`,
    };
  }
  return { ok: true };
}

/**
 * Estimate FPS from `requestVideoFrameCallback` samples (mediaTime seconds of
 * consecutive presented frames). Browsers expose no FPS property, so this is
 * best-effort; returns null when there aren't enough samples.
 */
export function estimateFps(mediaTimes: number[]): number | null {
  if (mediaTimes.length < 2) return null;
  const deltas: number[] = [];
  for (let i = 1; i < mediaTimes.length; i++) {
    const d = mediaTimes[i] - mediaTimes[i - 1];
    if (d > 0) deltas.push(d);
  }
  if (deltas.length === 0) return null;
  const mean = deltas.reduce((a, b) => a + b, 0) / deltas.length;
  const fps = 1 / mean;
  if (!Number.isFinite(fps) || fps < 1 || fps > 240) return null;
  return Math.round(fps * 10) / 10;
}

/**
 * Extract metadata from a video file in the browser: duration and dimensions
 * from `loadedmetadata`, FPS estimated by briefly playing the video muted and
 * sampling frame callbacks (~500ms). Never rejects on FPS failure — fps: null.
 */
export function extractVideoMetadata(file: File): Promise<VideoMetadata> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement('video');
    video.preload = 'metadata';
    video.muted = true;
    video.playsInline = true;

    let settled = false;
    // Some codecs (e.g. HEVC on browsers without support) leave the element
    // stuck loading with neither loadedmetadata nor error — never hang the UI.
    const guard = setTimeout(() => {
      if (!settled) {
        settled = true;
        URL.revokeObjectURL(url);
        reject(new Error('Could not read this video in the browser.'));
      }
    }, 6000);

    const finish = (fps: number | null) => {
      if (settled) return;
      settled = true;
      clearTimeout(guard);
      const meta: VideoMetadata = {
        duration_sec: video.duration,
        width: video.videoWidth || null,
        height: video.videoHeight || null,
        fps,
        size_bytes: file.size,
      };
      URL.revokeObjectURL(url);
      video.src = '';
      resolve(meta);
    };

    video.onerror = () => {
      if (settled) return;
      settled = true;
      clearTimeout(guard);
      URL.revokeObjectURL(url);
      reject(new Error('Could not read this video file.'));
    };

    video.onloadedmetadata = () => {
      const rvfc = (video as any).requestVideoFrameCallback?.bind(video);
      if (!rvfc) {
        finish(null);
        return;
      }
      const samples: number[] = [];
      const deadline = setTimeout(() => finish(estimateFps(samples)), 700);
      const onFrame = (_now: number, frameMeta: { mediaTime: number }) => {
        samples.push(frameMeta.mediaTime);
        if (samples.length >= 12) {
          clearTimeout(deadline);
          video.pause();
          finish(estimateFps(samples));
        } else {
          rvfc(onFrame);
        }
      };
      rvfc(onFrame);
      video.play().catch(() => {
        clearTimeout(deadline);
        finish(null);
      });
    };

    video.src = url;
  });
}
