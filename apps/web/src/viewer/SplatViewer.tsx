import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';
import { useEffect, useRef, useState } from 'react';

import { FirstPersonControls } from './FirstPersonControls';

interface Props {
  splatUrl: string;
  onError?: (message: string) => void;
}

/**
 * Wraps @mkkellogg/gaussian-splats-3d in mobile-friendly defaults:
 * progressive loading (blurry -> sharp within seconds), capped pixel ratio
 * for 60 FPS on phones, no COOP/COEP requirement (sharedMemoryForWorkers off),
 * and our first-person touch controls instead of orbit controls.
 */
export default function SplatViewer({ splatUrl, onError }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;

    let disposed = false;
    let controls: FirstPersonControls | null = null;
    let raf = 0;

    // Dev/QA overrides: /tour/xyz?pos=0,1.5,2.2&look=0,1,0&nocontrols=1
    const params = new URLSearchParams(window.location.search);
    const vec = (name: string, fallback: [number, number, number]) => {
      const raw = params.get(name)?.split(',').map(Number);
      return raw && raw.length === 3 && raw.every(Number.isFinite)
        ? (raw as [number, number, number])
        : fallback;
    };

    const viewer = new GaussianSplats3D.Viewer({
      rootElement: root,
      cameraUp: [0, 1, 0],
      initialCameraPosition: vec('pos', [0, 1.5, 2.2]),
      initialCameraLookAt: vec('look', [0, 1.2, 0]),
      useBuiltInControls: false,
      selfDrivenMode: true,
      sharedMemoryForWorkers: false,
      // The default radial reveal animation advances per frame, so on slower
      // devices the scene looks clipped for many seconds. Progressive loading
      // already gives the blurry->sharp effect we want; reveal instantly.
      sceneRevealMode: GaussianSplats3D.SceneRevealMode.Instant,
    });
    viewer.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    if (import.meta.env.DEV) {
      (window as any).__viewer = viewer;
    }

    // Progressive loading requires HTTP range support (Content-Length +
    // Accept-Ranges); some static/dev servers lack it, so probe first and
    // load once in the right mode.
    const supportsRanges = fetch(splatUrl, { method: 'HEAD' })
      .then(
        (head) =>
          head.ok &&
          !!head.headers.get('content-length') &&
          (head.headers.get('accept-ranges') ?? '').includes('bytes'),
      )
      .catch(() => false);

    supportsRanges
      .then((progressive) =>
        viewer.addSplatScene(splatUrl, {
          progressiveLoad: progressive && !params.has('noprogressive'),
          showLoadingUI: true,
          splatAlphaRemovalThreshold: 5,
        }),
      )
      .then(() => {
        if (disposed) return;
        viewer.start();
        if (!params.has('nocontrols')) {
          controls = new FirstPersonControls(viewer.camera, viewer.renderer.domElement);
          const tick = () => {
            controls?.update();
            raf = requestAnimationFrame(tick);
          };
          raf = requestAnimationFrame(tick);
        }
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (!disposed) onError?.(e instanceof Error ? e.message : 'Failed to load the scene.');
      });

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      controls?.dispose();
      viewer.dispose().catch(() => {
        /* viewer may already be gone */
      });
    };
  }, [splatUrl, onError]);

  return (
    <div ref={containerRef} className="viewer-shell">
      {loading && (
        <div className="center">
          <div className="spinner" />
          <span>Preparing the space…</span>
        </div>
      )}
    </div>
  );
}
