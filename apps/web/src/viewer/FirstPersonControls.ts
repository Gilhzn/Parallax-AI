import * as THREE from 'three';

/**
 * Touch-first walk controls for splat tours:
 *  - drag        → look around (yaw / pitch, clamped)
 *  - tap         → glide one step forward along the horizontal view direction
 *  - pinch       → dolly forward / back
 *  - wheel       → dolly (desktop)
 *
 * The camera stays at eye height (locked Y) so the tour feels like walking,
 * not flying — the main lever against motion sickness alongside 60 FPS.
 */
export class FirstPersonControls {
  private camera: THREE.PerspectiveCamera;
  private element: HTMLElement;

  private yaw = 0;
  private pitch = 0;
  private readonly eyeHeight: number;

  private pointers = new Map<number, { x: number; y: number }>();
  private pinchDistance = 0;
  private downAt = 0;
  private downPos = { x: 0, y: 0 };
  private moved = false;

  private target: THREE.Vector3;
  private static readonly STEP = 1.0; // meters per tap
  private static readonly LOOK_SPEED = 0.005;
  private static readonly MAX_PITCH = THREE.MathUtils.degToRad(80);

  private disposers: (() => void)[] = [];

  constructor(camera: THREE.PerspectiveCamera, element: HTMLElement) {
    this.camera = camera;
    this.element = element;
    this.eyeHeight = camera.position.y;
    this.target = camera.position.clone();

    const euler = new THREE.Euler().setFromQuaternion(camera.quaternion, 'YXZ');
    this.yaw = euler.y;
    this.pitch = euler.x;

    this.bind('pointerdown', this.onPointerDown);
    this.bind('pointermove', this.onPointerMove);
    this.bind('pointerup', this.onPointerUp);
    this.bind('pointercancel', this.onPointerUp);
    this.bind('wheel', this.onWheel, { passive: false });
    element.style.touchAction = 'none';
  }

  private bind<K extends keyof HTMLElementEventMap>(
    type: K,
    handler: (e: HTMLElementEventMap[K]) => void,
    options?: AddEventListenerOptions,
  ) {
    const bound = handler.bind(this) as EventListener;
    this.element.addEventListener(type, bound, options);
    this.disposers.push(() => this.element.removeEventListener(type, bound));
  }

  private onPointerDown(e: PointerEvent) {
    this.element.setPointerCapture(e.pointerId);
    this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (this.pointers.size === 1) {
      this.downAt = performance.now();
      this.downPos = { x: e.clientX, y: e.clientY };
      this.moved = false;
    } else if (this.pointers.size === 2) {
      this.pinchDistance = this.currentPinchDistance();
    }
  }

  private onPointerMove(e: PointerEvent) {
    const prev = this.pointers.get(e.pointerId);
    if (!prev) return;
    const dx = e.clientX - prev.x;
    const dy = e.clientY - prev.y;
    this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

    if (this.pointers.size === 1) {
      if (Math.abs(e.clientX - this.downPos.x) + Math.abs(e.clientY - this.downPos.y) > 10) {
        this.moved = true;
      }
      // "Grab the world": the scene follows the finger (drag right -> look left),
      // matching the touch convention of maps and panorama viewers.
      this.yaw += dx * FirstPersonControls.LOOK_SPEED;
      this.pitch = THREE.MathUtils.clamp(
        this.pitch + dy * FirstPersonControls.LOOK_SPEED,
        -FirstPersonControls.MAX_PITCH,
        FirstPersonControls.MAX_PITCH,
      );
    } else if (this.pointers.size === 2) {
      const distance = this.currentPinchDistance();
      if (this.pinchDistance > 0) {
        this.dolly((distance - this.pinchDistance) * 0.01);
      }
      this.pinchDistance = distance;
      this.moved = true;
    }
  }

  private onPointerUp(e: PointerEvent) {
    this.pointers.delete(e.pointerId);
    this.pinchDistance = 0;
    const quick = performance.now() - this.downAt < 300;
    if (this.pointers.size === 0 && quick && !this.moved) {
      this.dolly(FirstPersonControls.STEP);
    }
  }

  private onWheel(e: WheelEvent) {
    e.preventDefault();
    this.dolly(-e.deltaY * 0.0025);
  }

  private currentPinchDistance(): number {
    const [a, b] = [...this.pointers.values()];
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  /** Glide along the horizontal projection of the view direction. */
  private dolly(meters: number) {
    const forward = new THREE.Vector3(-Math.sin(this.yaw), 0, -Math.cos(this.yaw));
    this.target.addScaledVector(forward, meters);
    this.target.y = this.eyeHeight;
  }

  /** Call once per frame. */
  update() {
    this.camera.quaternion.setFromEuler(new THREE.Euler(this.pitch, this.yaw, 0, 'YXZ'));
    // Ease toward the movement target for a smooth glide.
    this.camera.position.lerp(this.target, 0.12);
    this.camera.position.y = this.eyeHeight;
  }

  dispose() {
    this.disposers.forEach((d) => d());
    this.disposers = [];
    this.pointers.clear();
  }
}
