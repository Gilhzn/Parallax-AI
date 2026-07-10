export interface VideoMetadata {
  duration_sec: number;
  width: number | null;
  height: number | null;
  fps: number | null;
  size_bytes: number;
}

export interface JobStatus {
  job_id: string;
  status: 'queued' | 'processing' | 'done' | 'error';
  stage: string | null;
  progress: number;
  error: string | null;
  tour_url: string | null;
}

export interface Tour {
  job_id: string;
  splat_url: string;
  manifest: Record<string, unknown>;
}

const BASE = import.meta.env.VITE_API_BASE ?? '';

// ── Demo mode ──────────────────────────────────────────────────────────────
// When no backend is reachable (e.g. the static GitHub Pages deployment),
// the app falls back to a client-side simulation: the job advances through
// the real pipeline stages on a timer and the tour shows the sample scene.
// Demo jobs are clearly marked so the UI can label them.

export const DEMO_JOB_ID = 'demo';
// Static deployments (GitHub Pages) build with VITE_DEMO_MODE=1: no backend
// exists at all, so uploads skip the network entirely.
const FORCED_DEMO = import.meta.env.VITE_DEMO_MODE === '1';
export const IS_DEMO_BUILD = FORCED_DEMO;

// Where to upload a video for a REAL (free, CPU) reconstruction — the
// GitHub Actions workflow picks it up and publishes the tour to this site.
export const REAL_RECONSTRUCTION_UPLOAD_URL =
  'https://github.com/Gilhzn/Parallax-AI/upload/claude/spatialscan-platform-arch-agtxzq/captures';
const DEMO_START_KEY = 'spatialscan-demo-start';
const DEMO_STAGES: { stage: string; until: number }[] = [
  { stage: 'upload', until: 0.1 },
  { stage: 'frames', until: 0.25 },
  { stage: 'poses', until: 0.5 },
  { stage: 'training', until: 0.9 },
  { stage: 'export', until: 1.0 },
];
const DEMO_DURATION_MS = 9000;

export function isDemoJob(jobId: string): boolean {
  return jobId === DEMO_JOB_ID;
}

function startDemoJob(): { job_id: string } {
  sessionStorage.setItem(DEMO_START_KEY, String(Date.now()));
  return { job_id: DEMO_JOB_ID };
}

function demoStatus(): JobStatus {
  const start = Number(sessionStorage.getItem(DEMO_START_KEY) ?? Date.now());
  const progress = Math.min((Date.now() - start) / DEMO_DURATION_MS, 1);
  const stage = DEMO_STAGES.find((s) => progress <= s.until)?.stage ?? 'export';
  const done = progress >= 1;
  return {
    job_id: DEMO_JOB_ID,
    status: done ? 'done' : 'processing',
    stage: done ? 'export' : stage,
    progress,
    error: null,
    tour_url: done ? `/tour/${DEMO_JOB_ID}` : null,
  };
}

function demoTour(): Tour {
  return {
    job_id: DEMO_JOB_ID,
    splat_url: `${import.meta.env.BASE_URL}sample.splat`,
    manifest: { demo: true, note: 'Client-side demo — no backend connected' },
  };
}

// Static tours: real reconstructions published into public/tours/ by the
// free CPU reconstruction workflow (.github/workflows/reconstruct.yml).
function staticTour(tourId: string): Tour {
  return {
    job_id: tourId,
    splat_url: `${import.meta.env.BASE_URL}tours/${encodeURIComponent(tourId)}.splat`,
    manifest: { static: true },
  };
}
// ───────────────────────────────────────────────────────────────────────────

async function ensureOk(resp: Response): Promise<Response> {
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (body.detail) detail = String(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return resp;
}

export type QualityPreset = 'fast' | 'balanced' | 'high';

export async function createJob(
  video: File,
  metadata: VideoMetadata,
  quality: QualityPreset = 'balanced',
): Promise<{ job_id: string }> {
  if (FORCED_DEMO) return startDemoJob();
  const form = new FormData();
  form.append('video', video);
  form.append('metadata', JSON.stringify(metadata));
  form.append('quality', quality);
  try {
    const resp = await ensureOk(await fetch(`${BASE}/api/jobs`, { method: 'POST', body: form }));
    return resp.json();
  } catch (e) {
    // Server-side rejections (413/415/422...) surface to the user; only a
    // network-level failure (no backend at all) activates demo mode.
    if (e instanceof TypeError) return startDemoJob();
    throw e;
  }
}

export async function getJob(jobId: string): Promise<JobStatus> {
  if (isDemoJob(jobId)) return demoStatus();
  const resp = await ensureOk(await fetch(`${BASE}/api/jobs/${jobId}`));
  return resp.json();
}

export async function getTour(jobId: string): Promise<Tour> {
  if (isDemoJob(jobId)) return demoTour();
  if (FORCED_DEMO) return staticTour(jobId);
  try {
    const resp = await ensureOk(await fetch(`${BASE}/api/tours/${jobId}`));
    return resp.json();
  } catch (e) {
    if (e instanceof TypeError) return staticTour(jobId); // no backend at all
    throw e;
  }
}
