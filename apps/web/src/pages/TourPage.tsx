import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { getTour } from '../api/client';
import SplatViewer from '../viewer/SplatViewer';

export default function TourPage() {
  const { tourId } = useParams<{ tourId: string }>();
  const [splatUrl, setSplatUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shared, setShared] = useState(false);

  useEffect(() => {
    if (!tourId) return;
    if (tourId === 'sample') {
      // Committed demo scene — works with no backend at all.
      setSplatUrl('/sample.splat');
      return;
    }
    getTour(tourId)
      .then((tour) => setSplatUrl(tour.splat_url))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [tourId]);

  async function share() {
    const url = window.location.href;
    try {
      if (navigator.share) {
        await navigator.share({ title: 'SpatialScan tour', url });
      } else {
        await navigator.clipboard.writeText(url);
        setShared(true);
        setTimeout(() => setShared(false), 2000);
      }
    } catch {
      /* user dismissed the share sheet */
    }
  }

  if (error) {
    return (
      <div className="page">
        <div className="center" style={{ flex: 1 }}>
          <p className="error">{error}</p>
          <Link className="btn ghost" to="/">
            Back to upload
          </Link>
        </div>
      </div>
    );
  }

  return (
    <>
      {splatUrl && <SplatViewer splatUrl={splatUrl} onError={setError} />}
      <div className="viewer-hud">
        <Link className="chip" to="/">
          ← SpatialScan
        </Link>
        <button className="chip" onClick={share} style={{ cursor: 'pointer' }}>
          {shared ? 'Link copied ✓' : 'Share'}
        </button>
      </div>
      <div className="viewer-help chip">Drag to look · tap to walk · pinch to zoom</div>
    </>
  );
}
