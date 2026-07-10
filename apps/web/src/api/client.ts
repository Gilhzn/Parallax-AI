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
export const REPO = 'Gilhzn/Parallax-AI';
export const REPO_BRANCH = 'claude/spatialscan-platform-arch-agtxzq';
export const REAL_RECONSTRUCTION_UPLOAD_URL = `https://github.com/${REPO}/upload/${REPO_BRANCH}/captures`;
export const ACTIONS_URL = `https://github.com/${REPO}/actions/workflows/reconstruct.yml`;
// Fine-grained token: Only select repositories -> Parallax-AI; Contents: Read and write.
export const TOKEN_CREATE_URL = 'https://github.com/settings/personal-access-tokens/new';
// One-click classic token with the right scope preselected — the easy path.
export const TOKEN_QUICK_URL =
  'https://github.com/settings/tokens/new?scopes=repo&description=SpatialScan%20uploads';

/** Quick sanity check that a pasted value even looks like a GitHub token. */
export function looksLikeGithubToken(token: string): boolean {
  const t = token.trim();
  return /^(github_pat_[A-Za-z0-9_]{30,}|ghp_[A-Za-z0-9]{30,}|gho_[A-Za-z0-9]{30,})$/.test(t);
}

/** Redacted description of the token that will actually be sent — surfaces
 *  paste accidents (stale value, doubled paste) without exposing the secret. */
export function describeToken(token: string): string {
  const t = token.trim();
  if (!t) return 'empty';
  return `${t.slice(0, 10)}…${t.slice(-4)} · ${t.length} chars`;
}

async function githubMessage(resp: Response): Promise<string> {
  try {
    const body = await resp.json();
    return body?.message ? ` — GitHub says: "${body.message}"` : '';
  } catch {
    return '';
  }
}

/** Verify the token can see the repo AND is allowed to write to it. */
export async function verifyGithubToken(token: string): Promise<void> {
  let resp: Response;
  try {
    resp = await fetch(`https://api.github.com/repos/${REPO}`, {
      headers: { Authorization: `Bearer ${token.trim()}`, Accept: 'application/vnd.github+json' },
      cache: 'no-store',
    });
  } catch {
    throw new Error('Could not reach GitHub — check your connection and try again.');
  }
  if (resp.status === 401) {
    throw new Error(
      `GitHub rejected the token (invalid or expired)${await githubMessage(resp)}. ` +
        'Make sure you copied the ENTIRE token.',
    );
  }
  if (resp.status === 403 || resp.status === 404) {
    throw new Error(
      `The token has no access to the ${REPO} repository${await githubMessage(resp)}. ` +
        'Recreate it with the repo selected.',
    );
  }
  if (!resp.ok) {
    throw new Error(`GitHub token check failed (HTTP ${resp.status})${await githubMessage(resp)}.`);
  }
  // A valid token from the WRONG account (or one missing the repo scope)
  // can read a public repo but not write to it — catch that here, before
  // the upload, with a precise explanation.
  const repoInfo = await resp.json();
  if (repoInfo?.permissions?.push !== true) {
    throw new Error(
      'This token cannot WRITE to the repository. It probably belongs to a different GitHub ' +
        'account or is missing the "repo" scope — create the token while logged in as the ' +
        'repository owner (Gilhzn), using the quick link above.',
    );
  }
}

const TOKEN_KEY = 'spatialscan-github-token';

export function getGithubToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? '';
}

export function setGithubToken(token: string): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function sanitizeTourName(filename: string): string {
  const stem = filename.replace(/\.[^.]+$/, '');
  const clean = stem
    .toLowerCase()
    .replace(/[^a-z0-9-_]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
  return clean || 'tour';
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Could not read the video file.'));
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] ?? '');
    reader.readAsDataURL(file);
  });
}

export const MAX_REAL_UPLOAD_MB = 70; // GitHub contents API caps ~100MB after base64

/**
 * Queue a REAL reconstruction from inside the app: commits the video into
 * captures/ on the repo via the GitHub contents API (using the user's own
 * fine-grained token, stored only in this browser), which triggers the
 * reconstruction workflow. Returns the future tour name.
 */
export async function queueRealReconstruction(
  video: File,
  token: string,
): Promise<{ name: string; tourUrl: string }> {
  if (video.size > MAX_REAL_UPLOAD_MB * 1024 * 1024) {
    throw new Error(
      `Video is ${(video.size / 1024 / 1024).toFixed(0)}MB — the in-app limit is ` +
        `${MAX_REAL_UPLOAD_MB}MB. Film a shorter clip or lower the resolution.`,
    );
  }
  const ext = (video.name.split('.').pop() || 'mp4').toLowerCase();
  const safeExt = ['mp4', 'mov', 'webm'].includes(ext) ? ext : 'mp4';
  const name = `${sanitizeTourName(video.name)}-${Date.now().toString(36).slice(-4)}`;
  const path = `captures/${name}.${safeExt}`;

  const resp = await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: `Queue real reconstruction: ${name}`,
      branch: REPO_BRANCH,
      content: await fileToBase64(video),
    }),
  });
  if (resp.status === 401) {
    throw new Error(
      `GitHub token is invalid or expired${await githubMessage(resp)} — paste a new one.`,
    );
  }
  if (resp.status === 403 || resp.status === 404) {
    throw new Error(
      `Token is not allowed to write to the repository${await githubMessage(resp)}. ` +
        'Create the token while logged in as the repository owner (Gilhzn).',
    );
  }
  if (!resp.ok) throw new Error(`GitHub upload failed (HTTP ${resp.status})${await githubMessage(resp)}.`);
  return { name, tourUrl: `/tour/${name}` };
}

/** True once the reconstruction workflow has published this tour. */
export async function tourReady(name: string): Promise<boolean> {
  try {
    const resp = await fetch(
      `${import.meta.env.BASE_URL}tours/${encodeURIComponent(name)}.json?t=${Date.now()}`,
      { cache: 'no-store' },
    );
    return resp.ok;
  } catch {
    return false;
  }
}
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
async function staticTour(tourId: string): Promise<Tour> {
  const base = `${import.meta.env.BASE_URL}tours/${encodeURIComponent(tourId)}`;
  let manifest: Record<string, unknown> = { static: true };
  try {
    const resp = await fetch(`${base}.json`);
    if (resp.ok) manifest = { static: true, ...(await resp.json()) };
  } catch {
    /* manifest is optional */
  }
  return { job_id: tourId, splat_url: `${base}.splat`, manifest };
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
