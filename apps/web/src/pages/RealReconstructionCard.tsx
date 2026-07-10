import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  ACTIONS_URL,
  getGithubToken,
  MAX_REAL_UPLOAD_MB,
  queueRealReconstruction,
  setGithubToken,
  TOKEN_CREATE_URL,
  tourReady,
} from '../api/client';

const POLL_MS = 45_000;

/**
 * In-app path to a REAL reconstruction: film/pick a video, send it straight
 * to the reconstruction queue (a commit into captures/ via the GitHub API,
 * authorized by the user's own token, stored only in this browser), then
 * watch until the tour is published to this site.
 */
export default function RealReconstructionCard({ video }: { video: File }) {
  const [token, setToken] = useState(getGithubToken());
  const [needToken, setNeedToken] = useState(!getGithubToken());
  const [busy, setBusy] = useState(false);
  const [queued, setQueued] = useState<{ name: string; tourUrl: string } | null>(null);
  const [ready, setReady] = useState(false);
  const [elapsedMin, setElapsedMin] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => () => clearInterval(pollRef.current), []);

  async function send() {
    setError(null);
    const tok = token.trim();
    if (!tok) {
      setNeedToken(true);
      return;
    }
    setBusy(true);
    try {
      setGithubToken(tok);
      const result = await queueRealReconstruction(video, tok);
      setQueued(result);
      const started = Date.now();
      pollRef.current = setInterval(async () => {
        setElapsedMin(Math.round((Date.now() - started) / 60000));
        if (await tourReady(result.name)) {
          setReady(true);
          clearInterval(pollRef.current);
        }
      }, POLL_MS);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      if (e instanceof Error && /token/i.test(e.message)) setNeedToken(true);
    } finally {
      setBusy(false);
    }
  }

  if (queued) {
    return (
      <div className="card" style={{ borderColor: 'var(--accent)' }}>
        {ready ? (
          <>
            <strong>✅ Your reconstruction is ready!</strong>
            <p className="hint" style={{ margin: '6px 0 10px' }}>
              The 3D model was built from your footage and published.
            </p>
            <Link className="btn" to={queued.tourUrl}>
              Walk through your tour →
            </Link>
          </>
        ) : (
          <>
            <strong>🛰️ Reconstruction queued — {queued.name}</strong>
            <p className="hint" style={{ margin: '6px 0 10px' }}>
              Your video is being turned into a real 3D model (COLMAP + Gaussian Splatting).
              This usually takes 15–60 minutes{elapsedMin > 0 ? ` — ${elapsedMin} min elapsed` : ''}.
              You can keep this page open (it updates automatically), or come back later to{' '}
              <Link to={queued.tourUrl}>{queued.tourUrl}</Link>.
            </p>
            <a className="btn ghost" href={ACTIONS_URL} target="_blank" rel="noreferrer">
              Watch progress on GitHub →
            </a>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="card" style={{ borderColor: 'var(--accent)' }}>
      <strong>Send to REAL reconstruction</strong>
      <p className="hint" style={{ margin: '6px 0 10px' }}>
        Builds an actual 3D model from your footage (free, 15–60 min) and publishes it to this
        site. Up to {MAX_REAL_UPLOAD_MB}MB.
      </p>

      {needToken && (
        <div style={{ marginBottom: 10 }}>
          <p className="hint" style={{ margin: '0 0 8px' }}>
            One-time setup: paste a GitHub token so the app may add your video to the
            reconstruction queue. It is stored only in this browser.{' '}
            <a href={TOKEN_CREATE_URL} target="_blank" rel="noreferrer">
              Create one here
            </a>{' '}
            — choose <em>Only select repositories → Parallax-AI</em> and set{' '}
            <em>Contents: Read and write</em>.
          </p>
          <input
            type="password"
            placeholder="github_pat_..."
            value={token}
            onChange={(e) => setToken(e.target.value)}
            style={{
              width: '100%',
              padding: '10px 12px',
              borderRadius: 10,
              border: '1px solid var(--border)',
              background: 'var(--bg)',
              color: 'var(--text)',
            }}
          />
        </div>
      )}

      {error && <p className="error" style={{ margin: '0 0 10px' }}>{error}</p>}

      <button className="btn" disabled={busy || (needToken && !token.trim())} onClick={send}>
        {busy ? 'Uploading to the queue…' : 'Reconstruct my video for real'}
      </button>
    </div>
  );
}
