/**
 * Edge Path Builder
 *
 * Computes SVG path `d` strings for directed edges between two positioned
 * rectangles.  Supports three routing modes: bezier, step, and straight.
 * Resolves connection ports on source/target rect boundaries and generates
 * arrowhead geometry.  Pure math — no DOM, no framework.
 */

export interface Vec2 {
  readonly x: number;
  readonly y: number;
}

export interface Rect {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export type PortSide = 'top' | 'bottom' | 'left' | 'right' | 'auto';
export type RoutingMode = 'bezier' | 'step' | 'straight';

export interface EdgePathOptions {
  /** Routing mode. Default: 'bezier'. */
  mode?: RoutingMode;
  /** Where the wire exits the source rect. Default: 'auto'. */
  sourcePort?: PortSide;
  /** Where the wire enters the target rect. Default: 'auto'. */
  targetPort?: PortSide;
  /** Arrowhead size in pixels. Default: 8. */
  arrowSize?: number;
  /** Arrowhead angle in radians. Default: Math.PI / 6. */
  arrowAngle?: number;
  /** Curvature intensity for bezier mode (0-1). Default: 0.5. */
  curvature?: number;
}

export interface ArrowheadResult {
  /** SVG path `d` string for the arrowhead polygon. */
  path: string;
  /** Position of the arrowhead tip (at the target port). */
  position: Vec2;
  /** Angle of the arrowhead in radians. */
  angle: number;
}

export interface EdgePathResult {
  /** SVG path `d` string for the edge line. */
  path: string;
  /** Arrowhead geometry. */
  arrowhead: ArrowheadResult;
  /** Resolved source connection point. */
  sourcePort: Vec2;
  /** Resolved target connection point. */
  targetPort: Vec2;
}

function rectCenter(rect: Rect): Vec2 {
  return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
}

function portPoint(rect: Rect, side: Exclude<PortSide, 'auto'>): Vec2 {
  const cx = rect.x + rect.width / 2;
  const cy = rect.y + rect.height / 2;
  switch (side) {
    case 'top':    return { x: cx, y: rect.y };
    case 'bottom': return { x: cx, y: rect.y + rect.height };
    case 'left':   return { x: rect.x, y: cy };
    case 'right':  return { x: rect.x + rect.width, y: cy };
  }
}

/**
 * Resolve 'auto' port by picking the side of the rect closest to the
 * other rect's center.
 */
export function resolvePort(rect: Rect, otherRect: Rect, side: PortSide): Vec2 {
  if (side !== 'auto') return portPoint(rect, side);

  const other = rectCenter(otherRect);
  const cx = rect.x + rect.width / 2;
  const cy = rect.y + rect.height / 2;
  const dx = other.x - cx;
  const dy = other.y - cy;

  // Prefer vertical ports when the vertical distance is larger
  if (Math.abs(dy) > Math.abs(dx)) {
    return dy > 0
      ? portPoint(rect, 'bottom')
      : portPoint(rect, 'top');
  }
  return dx > 0
    ? portPoint(rect, 'right')
    : portPoint(rect, 'left');
}

function buildStraightPath(src: Vec2, tgt: Vec2): string {
  return `M ${src.x} ${src.y} L ${tgt.x} ${tgt.y}`;
}

function buildBezierPath(src: Vec2, tgt: Vec2, curvature: number): string {
  const dx = tgt.x - src.x;
  const dy = tgt.y - src.y;
  const dist = Math.sqrt(dx * dx + dy * dy);
  const offset = dist * curvature;

  // Determine control point direction based on dominant axis
  let cp1: Vec2;
  let cp2: Vec2;

  if (Math.abs(dy) >= Math.abs(dx)) {
    // Vertical dominant: offset control points in Y
    const dir = dy >= 0 ? 1 : -1;
    cp1 = { x: src.x, y: src.y + offset * dir };
    cp2 = { x: tgt.x, y: tgt.y - offset * dir };
  } else {
    // Horizontal dominant: offset control points in X
    const dir = dx >= 0 ? 1 : -1;
    cp1 = { x: src.x + offset * dir, y: src.y };
    cp2 = { x: tgt.x - offset * dir, y: tgt.y };
  }

  return `M ${src.x} ${src.y} C ${cp1.x} ${cp1.y}, ${cp2.x} ${cp2.y}, ${tgt.x} ${tgt.y}`;
}

function buildStepPath(src: Vec2, tgt: Vec2): string {
  const midY = (src.y + tgt.y) / 2;
  return `M ${src.x} ${src.y} L ${src.x} ${midY} L ${tgt.x} ${midY} L ${tgt.x} ${tgt.y}`;
}

/**
 * Compute the arrowhead geometry at the target port.
 *
 * @param from - The point the path arrives from (last control point or source).
 * @param to - The arrowhead tip position (target port).
 * @param size - Arrow side length in pixels.
 * @param halfAngle - Half-angle of the arrowhead opening.
 */
export function buildArrowhead(
  from: Vec2,
  to: Vec2,
  size: number,
  halfAngle: number
): ArrowheadResult {
  const angle = Math.atan2(to.y - from.y, to.x - from.x);

  const leftX = to.x - size * Math.cos(angle - halfAngle);
  const leftY = to.y - size * Math.sin(angle - halfAngle);
  const rightX = to.x - size * Math.cos(angle + halfAngle);
  const rightY = to.y - size * Math.sin(angle + halfAngle);

  const path = `M ${to.x} ${to.y} L ${leftX} ${leftY} L ${rightX} ${rightY} Z`;

  return { path, position: to, angle };
}

/**
 * Build a complete edge path between two rectangles.
 */
export function buildEdgePath(
  sourceRect: Rect,
  targetRect: Rect,
  options: EdgePathOptions = {}
): EdgePathResult {
  const {
    mode = 'bezier',
    sourcePort: srcSide = 'auto',
    targetPort: tgtSide = 'auto',
    arrowSize = 8,
    arrowAngle = Math.PI / 6,
    curvature = 0.5,
  } = options;

  const src = resolvePort(sourceRect, targetRect, srcSide);
  const tgt = resolvePort(targetRect, sourceRect, tgtSide);

  let path: string;
  switch (mode) {
    case 'straight':
      path = buildStraightPath(src, tgt);
      break;
    case 'step':
      path = buildStepPath(src, tgt);
      break;
    case 'bezier':
    default:
      path = buildBezierPath(src, tgt, curvature);
      break;
  }

  const arrowhead = buildArrowhead(src, tgt, arrowSize, arrowAngle);

  return { path, arrowhead, sourcePort: src, targetPort: tgt };
}
