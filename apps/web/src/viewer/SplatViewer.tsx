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

    const viewer = new GaussianSplats3D.Viewer({
      rootElement: root,
      cameraUp: [0, 1, 0],
      initialCameraPosition: [0, 1.5, 2.2],
      initialCameraLookAt: [0, 1.2, 0],
      useBuiltInControls: false,
      selfDrivenMode: true,
      sharedMemoryForWorkers: false,
    });
    viewer.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    viewer
      .addSplatScene(splatUrl, {
        progressiveLoad: true,
        showLoadingUI: true,
        splatAlphaRemovalThreshold: 5,
      })
      .then(() => {
        if (disposed) return;
        viewer.start();
        controls = new FirstPersonControls(viewer.camera, viewer.renderer.domElement);
        const tick = () => {
          controls?.update();
          raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
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
