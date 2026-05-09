/**
 * Viewport Camera Store
 *
 * 2D camera state model with observable store for infinite pan/zoom
 * canvases.  Manages pan offset, zoom level, and viewport dimensions.
 * Provides screen↔world coordinate transforms, zoom-at-pointer, and
 * fit-to-bounds.  Pure math — no DOM, no framework.
 */

export interface Point2D {
  readonly x: number;
  readonly y: number;
}

export interface Rect2D {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export interface CameraState {
  readonly panX: number;
  readonly panY: number;
  readonly zoom: number;
  readonly viewportWidth: number;
  readonly viewportHeight: number;
}

export interface CameraOptions {
  /** Minimum zoom level (default 0.1). */
  minZoom?: number;
  /** Maximum zoom level (default 5). */
  maxZoom?: number;
  /** Initial pan X (default 0). */
  initialPanX?: number;
  /** Initial pan Y (default 0). */
  initialPanY?: number;
  /** Initial zoom (default 1). */
  initialZoom?: number;
}

export type CameraListener = (state: CameraState) => void;

/**
 * Observable 2D viewport camera.
 */
export class ViewportCameraStore {
  private _panX: number;
  private _panY: number;
  private _zoom: number;
  private _viewportWidth = 0;
  private _viewportHeight = 0;
  private _minZoom: number;
  private _maxZoom: number;
  private _listeners = new Set<CameraListener>();

  constructor(options: CameraOptions = {}) {
    this._panX = options.initialPanX ?? 0;
    this._panY = options.initialPanY ?? 0;
    this._zoom = options.initialZoom ?? 1;
    this._minZoom = options.minZoom ?? 0.1;
    this._maxZoom = options.maxZoom ?? 5;
  }

  /** Current camera state snapshot. */
  getState(): CameraState {
    return {
      panX: this._panX,
      panY: this._panY,
      zoom: this._zoom,
      viewportWidth: this._viewportWidth,
      viewportHeight: this._viewportHeight,
    };
  }

  /** Set the viewport dimensions (screen pixels). */
  setViewport(width: number, height: number): void {
    this._viewportWidth = width;
    this._viewportHeight = height;
    this._notify();
  }

  /**
   * Pan the camera by a screen-space delta.
   * Internally converts screen delta to world delta using current zoom.
   */
  pan(dx: number, dy: number): void {
    this._panX += dx;
    this._panY += dy;
    this._notify();
  }

  /**
   * Set the pan position directly (world coordinates).
   */
  setPan(panX: number, panY: number): void {
    this._panX = panX;
    this._panY = panY;
    this._notify();
  }

  /**
   * Set the zoom level, clamped to min/max.
   */
  setZoom(zoom: number): void {
    this._zoom = this._clampZoom(zoom);
    this._notify();
  }

  /**
   * Zoom toward a screen-space point (e.g., pointer position).
   * The world point under the pointer stays fixed.
   *
   * @param screenX - Pointer X in screen pixels.
   * @param screenY - Pointer Y in screen pixels.
   * @param delta - Zoom multiplier delta (e.g., 1.1 for zoom in, 0.9 for zoom out).
   */
  zoomAt(screenX: number, screenY: number, delta: number): void {
    const oldZoom = this._zoom;
    const newZoom = this._clampZoom(oldZoom * delta);
    if (newZoom === oldZoom) return;

    // World point under the cursor before zoom
    const worldBefore = this.screenToWorld(screenX, screenY);

    this._zoom = newZoom;

    // World point under the cursor after zoom (with new zoom but old pan)
    const worldAfter = this.screenToWorld(screenX, screenY);

    // Adjust pan so the world point stays under the cursor
    this._panX += (worldAfter.x - worldBefore.x) * newZoom;
    this._panY += (worldAfter.y - worldBefore.y) * newZoom;

    this._notify();
  }

  /**
   * Fit the camera to show a world-space rectangle with optional padding.
   *
   * @param rect - World-space bounding rectangle to fit.
   * @param padding - Padding in screen pixels (default 40).
   */
  fitBounds(rect: Rect2D, padding: number = 40): void {
    if (this._viewportWidth <= 0 || this._viewportHeight <= 0) return;

    const availW = this._viewportWidth - padding * 2;
    const availH = this._viewportHeight - padding * 2;

    if (availW <= 0 || availH <= 0) return;

    const scaleX = availW / rect.width;
    const scaleY = availH / rect.height;
    const newZoom = this._clampZoom(Math.min(scaleX, scaleY));

    // Center the rect in the viewport
    const centerX = rect.x + rect.width / 2;
    const centerY = rect.y + rect.height / 2;

    this._zoom = newZoom;
    this._panX = this._viewportWidth / 2 - centerX * newZoom;
    this._panY = this._viewportHeight / 2 - centerY * newZoom;

    this._notify();
  }

  /**
   * Convert screen pixel coordinates to world coordinates.
   */
  screenToWorld(screenX: number, screenY: number): Point2D {
    return {
      x: (screenX - this._panX) / this._zoom,
      y: (screenY - this._panY) / this._zoom,
    };
  }

  /**
   * Convert world coordinates to screen pixel coordinates.
   */
  worldToScreen(worldX: number, worldY: number): Point2D {
    return {
      x: worldX * this._zoom + this._panX,
      y: worldY * this._zoom + this._panY,
    };
  }

  /**
   * Get the visible world-space rectangle (viewport bounds in world coords).
   */
  getViewportBounds(): Rect2D {
    const topLeft = this.screenToWorld(0, 0);
    const bottomRight = this.screenToWorld(this._viewportWidth, this._viewportHeight);
    return {
      x: topLeft.x,
      y: topLeft.y,
      width: bottomRight.x - topLeft.x,
      height: bottomRight.y - topLeft.y,
    };
  }

  /**
   * Subscribe to camera state changes.
   * @returns An unsubscribe function.
   */
  subscribe(listener: CameraListener): () => void {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  private _clampZoom(zoom: number): number {
    return Math.min(this._maxZoom, Math.max(this._minZoom, zoom));
  }

  private _notify(): void {
    const state = this.getState();
    for (const listener of this._listeners) {
      listener(state);
    }
  }
}
