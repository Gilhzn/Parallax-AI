import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { createJob, type VideoMetadata } from '../api/client';
import { checkDuration, extractVideoMetadata, MAX_VIDEO_SECONDS } from '../lib/videoMetadata';

export default function UploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [meta, setMeta] = useState<VideoMetadata | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onPick(picked: File | undefined) {
    setError(null);
    setMeta(null);
    if (!picked) return;
    try {
      const extracted = await extractVideoMetadata(picked);
      const check = checkDuration(extracted.duration_sec);
      if (!check.ok) {
        setError(check.error!);
        setFile(null);
        return;
      }
      setFile(picked);
      setMeta(extracted);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function onUpload() {
    if (!file || !meta) return;
    setBusy(true);
    setError(null);
    try {
      const { job_id } = await createJob(file, meta);
      navigate(`/jobs/${job_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <a className="brand" href="/">
        <img src="/icon.svg" alt="" />
        <h1>SpatialScan</h1>
      </a>
      <p className="tagline">
        Film a room, get a walkable photorealistic 3D tour. No special hardware.
      </p>

      <div
        className="drop"
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
      >
        <span className="big">🎥</span>
        {file ? <strong>{file.name}</strong> : <strong>Record or choose a video</strong>}
        <p className="hint">
          Up to {MAX_VIDEO_SECONDS} seconds. Walk slowly, keep the camera moving sideways, and
          overlap what you film.
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="video/mp4,video/quicktime,video/webm"
          capture="environment"
          hidden
          onChange={(e) => onPick(e.target.files?.[0])}
        />
      </div>

      {meta && (
        <div className="card">
          <div className="meta-row">
            <span>Duration</span>
            <span>{meta.duration_sec.toFixed(1)}s</span>
          </div>
          <div className="meta-row">
            <span>Resolution</span>
            <span>
              {meta.width ?? '?'}×{meta.height ?? '?'}
            </span>
          </div>
          <div className="meta-row">
            <span>Frame rate</span>
            <span>{meta.fps ? `~${meta.fps} fps` : 'unknown'}</span>
          </div>
          <div className="meta-row">
            <span>Size</span>
            <span>{(meta.size_bytes / 1024 / 1024).toFixed(1)} MB</span>
          </div>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      <div style={{ marginTop: 16, display: 'grid', gap: 10 }}>
        <button className="btn" disabled={!file || busy} onClick={onUpload}>
          {busy ? 'Uploading…' : 'Create 3D tour'}
        </button>
        <Link className="btn ghost" to="/tour/sample">
          Explore a demo tour
        </Link>
      </div>
    </div>
  );
}
