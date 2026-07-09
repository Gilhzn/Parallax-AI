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

export async function createJob(video: File, metadata: VideoMetadata): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append('video', video);
  form.append('metadata', JSON.stringify(metadata));
  const resp = await ensureOk(await fetch(`${BASE}/api/jobs`, { method: 'POST', body: form }));
  return resp.json();
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const resp = await ensureOk(await fetch(`${BASE}/api/jobs/${jobId}`));
  return resp.json();
}

export async function getTour(jobId: string): Promise<Tour> {
  const resp = await ensureOk(await fetch(`${BASE}/api/tours/${jobId}`));
  return resp.json();
}
