/**
 * Canvas Grid Pattern
 *
 * Generates dot-grid background data for an infinite pan/zoom canvas.
 * Adapts dot density and size to zoom level.  Returns either an array
 * of visible dots or a CSS radial-gradient string.
 * Pure math — no DOM, no rendering.
 */

export interface GridCamera {
  readonly panX: number;
  readonly panY: number;
  readonly zoom: number;
  readonly viewportWidth: number;
  readonly viewportHeight: number;
}

export interface GridDot {
  /** Screen X position. */
  readonly sx: number;
  /** Screen Y position. */
  readonly sy: number;
  /** Dot radius in screen pixels. */
  readonly radius: number;
  /** Opacity (0–1). */
  readonly opacity: number;
}

export interface GridPatternOptions {
  /** Base grid spacing in world pixels (default 20). */
  baseSpacing?: number;
  /** Base dot radius in screen pixels at zoom=1 (default 1). */
  dotRadius?: number;
  /** Dot color as CSS string (default 'var(--color-border-soft, #d0d0d0)'). */
  dotColor?: string;
  /** Zoom threshold below which dots begin fading (default 0.4). */
  fadeZoomThreshold?: number;
  /** Zoom threshold below which the coarse grid replaces the fine grid (default 0.2). */
  coarseZoomThreshold?: number;
  /** Multiplier for coarse grid spacing (default 5). */
  coarseMultiplier?: number;
}

const DEFAULTS: Required<GridPatternOptions> = {
  baseSpacing: 20,
  dotRadius: 1,
  dotColor: 'var(--color-border-soft, #d0d0d0)',
  fadeZoomThreshold: 0.4,
  coarseZoomThreshold: 0.2,
  coarseMultiplier: 5,
};

function resolveOptions(opts?: GridPatternOptions): Required<GridPatternOptions> {
  return { ...DEFAULTS, ...opts };
}

/**
 * Generate visible grid dots for the current camera state.
 *
 * Returns only dots within the viewport bounds (+ small margin).
 * Adapts density: when zoom < fadeZoomThreshold, dots begin fading;
 * when zoom < coarseZoomThreshold, a coarser grid takes over.
 */
export function generateGridDots(
  camera: GridCamera,
  options?: GridPatternOptions
): readonly GridDot[] {
  const opts = resolveOptions(options);
  const { panX, panY, zoom, viewportWidth, viewportHeight } = camera;

  // Pick the active spacing level
  let spacing = opts.baseSpacing;
  if (zoom < opts.coarseZoomThreshold) {
    spacing = opts.baseSpacing * opts.coarseMultiplier;
  }

  // Compute opacity based on zoom
  let opacity = 1;
  if (zoom < opts.fadeZoomThreshold) {
    opacity = Math.max(0, zoom / opts.fadeZoomThreshold);
  }

  if (opacity <= 0) return [];

  const screenSpacing = spacing * zoom;

  // Skip if dots would be too dense (less than 4px apart)
  if (screenSpacing < 4) return [];

  // World-space viewport bounds
  const worldLeft = -panX / zoom;
  const worldTop = -panY / zoom;
  const worldRight = (viewportWidth - panX) / zoom;
  const worldBottom = (viewportHeight - panY) / zoom;

  // Snap to grid
  const startX = Math.floor(worldLeft / spacing) * spacing;
  const startY = Math.floor(worldTop / spacing) * spacing;
  const endX = Math.ceil(worldRight / spacing) * spacing;
  const endY = Math.ceil(worldBottom / spacing) * spacing;

  const dots: GridDot[] = [];
  const radius = opts.dotRadius;

  for (let wx = startX; wx <= endX; wx += spacing) {
    for (let wy = startY; wy <= endY; wy += spacing) {
      const sx = wx * zoom + panX;
      const sy = wy * zoom + panY;
      dots.push({ sx, sy, radius, opacity });
    }
  }

  return dots;
}

/**
 * Generate a CSS background style for the dot grid.
 *
 * More performant than rendering individual dots for large viewports.
 * Returns a CSS object with `backgroundImage`, `backgroundSize`, and
 * `backgroundPosition` suitable for applying to a container div.
 */
export function gridPatternCss(
  camera: GridCamera,
  options?: GridPatternOptions
): { backgroundImage: string; backgroundSize: string; backgroundPosition: string } {
  const opts = resolveOptions(options);
  const { panX, panY, zoom } = camera;

  let spacing = opts.baseSpacing;
  if (zoom < opts.coarseZoomThreshold) {
    spacing = opts.baseSpacing * opts.coarseMultiplier;
  }

  let opacity = 1;
  if (zoom < opts.fadeZoomThreshold) {
    opacity = Math.max(0, zoom / opts.fadeZoomThreshold);
  }

  const screenSpacing = spacing * zoom;
  const radius = opts.dotRadius;

  // Use transparent dots when faded
  const color = opacity < 1
    ? `rgba(180, 180, 180, ${opacity.toFixed(3)})`
    : opts.dotColor;

  return {
    backgroundImage: `radial-gradient(circle, ${color} ${radius}px, transparent ${radius}px)`,
    backgroundSize: `${screenSpacing}px ${screenSpacing}px`,
    backgroundPosition: `${panX % screenSpacing}px ${panY % screenSpacing}px`,
  };
}
