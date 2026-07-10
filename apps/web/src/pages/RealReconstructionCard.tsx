import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  ACTIONS_URL,
  describeToken,
  getGithubToken,
  looksLikeGithubToken,
  MAX_REAL_UPLOAD_MB,
  queueRealReconstruction,
  setGithubToken,
  TOKEN_CREATE_URL,
  TOKEN_QUICK_URL,
  tourReady,
  verifyGithubToken,
} from '../api/client';

const POLL_MS = 45_000;

/**
 * In-app path to a REAL reconstruction: film/pick a video, send it straight
 * to the reconstruction queue (a commit into captures/ via the GitHub API,
 * authorized by the user's own token, stored only in this browser), then
 * watch until the tour is published to this site.
 *
 * Token handling is deliberately paranoid: the input is never prefilled with
 * a stored value (a stale bad token used to be re-sent invisibly, and mobile
 * paste APPENDS to existing content), a rejected token is wiped everywhere,
 * and the exact redacted value about to be used is always shown.
 */
export default function RealReconstructionCard({ video }: { video: File }) {
  const [token, setToken] = useState('');
  // 'unknown' until the stored token is verified in the background.
  const [storedState, setStoredState] = useState<'none' | 'checking' | 'valid'>(
    getGithubToken() ? 'checking' : 'none',
  );
  const [busy, setBusy] = useState(false);
  const [tokenOwner, setTokenOwner] = useState<string | null>(null);
  const [queued, setQueued] = useState<{ name: string; tourUrl: string } | null>(null);
  const [ready, setReady] = useState(false);
  const [elapsedMin, setElapsedMin] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    // Validate any remembered token once; silently discard it when GitHub
    // rejects it so the user always starts from a clean, empty field.
    const stored = getGithubToken();
    if (!stored) return;
    let cancelled = false;
    verifyGithubToken(stored)
      .then(({ login }) => {
        if (!cancelled) {
          setTokenOwner(login);
          setStoredState('valid');
        }
      })
      .catch(() => {
        setGithubToken('');
        if (!cancelled) {
          setStoredState('none');
          setError('The previously saved token was rejected by GitHub and has been removed — paste a fresh one.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => () => clearInterval(pollRef.current), []);

  function rejectToken(message: string) {
    setGithubToken('');
    setToken('');
    setStoredState('none');
    setError(message);
  }

  async function send() {
    setError(null);
    const tok = (storedState === 'valid' ? getGithubToken() : token).trim();
    if (!tok) {
      setError('Paste a GitHub token first.');
      return;
    }
    if (!looksLikeGithubToken(tok)) {
      rejectToken(
        `That does not look like a complete GitHub token (got: ${describeToken(tok)}). ` +
          'It should start with github_pat_ or ghp_ — tap the copy icon next to the token on ' +
          'GitHub and paste into an EMPTY field.',
      );
      return;
    }
    setBusy(true);
    try {
      const { login } = await verifyGithubToken(tok);
      setTokenOwner(login);
      setGithubToken(tok);
      setStoredState('valid');
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
      const msg = e instanceof Error ? e.message : String(e);
      if (/rejected|invalid|expired|no access/i.test(msg)) {
        rejectToken(`${msg} (token used: ${describeToken(tok)})`);
      } else {
        setError(msg);
      }
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

      {storedState === 'valid' ? (
        <p className="hint" style={{ margin: '0 0 10px' }}>
          🔑 Using your saved token{tokenOwner ? ` of @${tokenOwner}` : ''} (
          {describeToken(getGithubToken())}) — verified, write access confirmed.{' '}
          <a
            href="#clear"
            onClick={(e) => {
              e.preventDefault();
              rejectToken('Saved token cleared — paste a new one.');
            }}
          >
            Clear it
          </a>
        </p>
      ) : (
        <div style={{ marginBottom: 10 }}>
          <p className="hint" style={{ margin: '0 0 8px' }}>
            One-time setup: paste a GitHub token so the app may add your video to the
            reconstruction queue. It is stored only in this browser.
          </p>
          <p className="hint" style={{ margin: '0 0 8px' }}>
            <strong>Easiest:</strong>{' '}
            <a href={TOKEN_QUICK_URL} target="_blank" rel="noreferrer">
              open this link
            </a>
            , scroll down, press the green <em>Generate token</em> button, then tap the{' '}
            <em>copy icon</em> next to the value that starts with <code>ghp_</code> and paste it
            below.
          </p>
          <p className="hint" style={{ margin: '0 0 8px' }}>
            (Advanced, more restricted:{' '}
            <a href={TOKEN_CREATE_URL} target="_blank" rel="noreferrer">
              fine-grained token
            </a>{' '}
            with <em>Only select repositories → Parallax-AI</em> and <em>Contents: Read and
            write</em>.)
          </p>
          <input
            type="password"
            placeholder="github_pat_... / ghp_..."
            value={token}
            autoComplete="off"
            onChange={(e) => setToken(e.target.value)}
            onFocus={(e) => e.target.select()}
            style={{
              width: '100%',
              padding: '10px 12px',
              borderRadius: 10,
              border: '1px solid var(--border)',
              background: 'var(--bg)',
              color: 'var(--text)',
            }}
          />
          {token.trim() && (
            <p className="hint" style={{ margin: '6px 0 0' }}>
              Will send: {describeToken(token)}{' '}
              {!looksLikeGithubToken(token) && '⚠️ does not look like a full token yet'}
            </p>
          )}
        </div>
      )}

      {error && <p className="error" style={{ margin: '0 0 10px' }}>{error}</p>}

      <button
        className="btn"
        disabled={busy || (storedState !== 'valid' && !token.trim())}
        onClick={send}
      >
        {busy ? 'Checking & uploading…' : 'Reconstruct my video for real'}
      </button>
    </div>
  );
}
