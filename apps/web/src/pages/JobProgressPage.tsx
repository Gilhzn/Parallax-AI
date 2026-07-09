import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { getJob, type JobStatus } from '../api/client';

const STEPS: { key: string; label: string; detail: string }[] = [
  { key: 'upload', label: 'Uploaded', detail: 'Video stored securely' },
  { key: 'frames', label: 'Extracting frames', detail: '~3 frames per second' },
  { key: 'poses', label: 'Solving camera path', detail: 'COLMAP structure-from-motion' },
  { key: 'training', label: 'Training 3D model', detail: 'Gaussian Splatting optimization' },
  { key: 'export', label: 'Packaging tour', detail: 'Compressing to .splat' },
];

const POLL_MS = 2000;

export default function JobProgressPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const status = await getJob(jobId!);
        if (stopped) return;
        setJob(status);
        if (status.status === 'done') {
          navigate(`/tour/${jobId}`);
          return;
        }
        if (status.status !== 'error') {
          timer = setTimeout(poll, POLL_MS);
        }
      } catch (e) {
        if (!stopped) setError(e instanceof Error ? e.message : String(e));
      }
    }

    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [jobId, navigate]);

  const stageIndex = job?.stage ? STEPS.findIndex((s) => s.key === job.stage) : 0;
  const failed = job?.status === 'error' || !!error;

  return (
    <div className="page">
      <Link className="brand" to="/">
        <img src="/icon.svg" alt="" />
        <h1>SpatialScan</h1>
      </Link>
      <p className="tagline">Building your tour — this usually takes a few minutes.</p>

      <div className="card">
        <div className="bar">
          <div style={{ width: `${Math.round((job?.progress ?? 0) * 100)}%` }} />
        </div>
        <ol className="stepper">
          {STEPS.map((step, i) => {
            const cls =
              i < stageIndex || job?.status === 'done'
                ? 'done'
                : i === stageIndex && !failed
                  ? 'active'
                  : '';
            return (
              <li key={step.key} className={`step ${cls}`}>
                <span className="dot">{cls === 'done' ? '✓' : i + 1}</span>
                <span>
                  <strong>{step.label}</strong>
                  <br />
                  <small className="hint">{step.detail}</small>
                </span>
              </li>
            );
          })}
        </ol>
      </div>

      {failed && (
        <div className="card">
          <p className="error">{job?.error ?? error ?? 'Something went wrong.'}</p>
          <Link className="btn ghost" to="/">
            Try another video
          </Link>
        </div>
      )}
    </div>
  );
}
