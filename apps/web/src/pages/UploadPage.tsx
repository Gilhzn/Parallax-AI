import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { createJob, type QualityPreset, type VideoMetadata } from '../api/client';
import { checkDuration, extractVideoMetadata, MAX_VIDEO_SECONDS } from '../lib/videoMetadata';

const QUALITY_OPTIONS: { value: QualityPreset; label: string; hint: string }[] = [
  { value: 'fast', label: 'Fast', hint: '~3 min · preview quality' },
  { value: 'balanced', label: 'Balanced', hint: '~7 min · great quality' },
  { value: 'high', label: 'Maximum', hint: '~30 min · full resolution, no compromises' },
];

export default function UploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [meta, setMeta] = useState<VideoMetadata | null>(null);
  const [quality, setQuality] = useState<QualityPreset>('balanced');
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
      const { job_id } = await createJob(file, meta, quality);
      navigate(`/jobs/${job_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <a className="brand" href="/">
        <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" />
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

      {file && (
        <div className="card" role="radiogroup" aria-label="Reconstruction quality">
          <p className="hint" style={{ margin: '0 0 10px' }}>
            Reconstruction quality
          </p>
          {QUALITY_OPTIONS.map((opt) => (
            <label key={opt.value} className="quality-row">
              <input
                type="radio"
                name="quality"
                value={opt.value}
                checked={quality === opt.value}
                onChange={() => setQuality(opt.value)}
              />
              <span>
                <strong>{opt.label}</strong>
                <br />
                <small className="hint">{opt.hint}</small>
              </span>
            </label>
          ))}
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
