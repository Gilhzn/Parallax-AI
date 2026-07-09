declare module '@mkkellogg/gaussian-splats-3d' {
  import type * as THREE from 'three';

  export interface ViewerOptions {
    rootElement?: HTMLElement;
    cameraUp?: [number, number, number];
    initialCameraPosition?: [number, number, number];
    initialCameraLookAt?: [number, number, number];
    useBuiltInControls?: boolean;
    selfDrivenMode?: boolean;
    sharedMemoryForWorkers?: boolean;
    antialiased?: boolean;
    halfPrecisionCovariancesOnGPU?: boolean;
    [key: string]: unknown;
  }

  export interface AddSplatSceneOptions {
    progressiveLoad?: boolean;
    showLoadingUI?: boolean;
    splatAlphaRemovalThreshold?: number;
    position?: [number, number, number];
    rotation?: [number, number, number, number];
    scale?: [number, number, number];
    onProgress?: (percent: number, label: string, stage: number) => void;
    [key: string]: unknown;
  }

  export class Viewer {
    constructor(options?: ViewerOptions);
    camera: THREE.PerspectiveCamera;
    renderer: THREE.WebGLRenderer;
    addSplatScene(url: string, options?: AddSplatSceneOptions): Promise<void>;
    start(): void;
    stop(): void;
    dispose(): Promise<void>;
  }
}
