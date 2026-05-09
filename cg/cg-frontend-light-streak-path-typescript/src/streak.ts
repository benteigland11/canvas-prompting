/**
 * light_streak_path — generates a traveling path segment along a line or curve.
 *
 * Given start/end points and a progress value (0..1), returns a path data
 * string for a streak of light that grows and then shrinks as it travels.
 *
 * Supports an optional `pathFn` for arbitrary curved paths — when provided,
 * the streak samples the curve instead of interpolating linearly.
 */

export interface Vec2 {
  readonly x: number;
  readonly y: number;
}

/**
 * A function that samples a point on a path at parameter t ∈ [0, 1].
 * t=0 is the start, t=1 is the end.
 */
export type PathSampler = (t: number) => Vec2;

/**
 * Returns path data for a streak along a straight line.
 * progress: 0..1 (entire travel)
 * lengthFraction: 0.1..0.5 (how long the streak is)
 */
export function getLightStreak(
  start: Vec2,
  end: Vec2,
  progress: number,
  lengthFraction: number = 0.3
): string | null {
  if (progress <= 0 || progress >= 1.0) return null;

  const linearSampler: PathSampler = (t: number) => ({
    x: start.x + (end.x - start.x) * t,
    y: start.y + (end.y - start.y) * t,
  });

  return getCurvedStreak(linearSampler, progress, lengthFraction);
}

/**
 * Returns path data for a streak along an arbitrary curved path.
 *
 * @param pathFn - Samples a point on the curve at parameter t ∈ [0, 1].
 * @param progress - 0..1, how far the streak head has traveled.
 * @param lengthFraction - 0.1..0.5, streak length as a fraction of total path.
 * @param segments - Number of line segments to approximate the curved streak (default 8).
 */
export function getCurvedStreak(
  pathFn: PathSampler,
  progress: number,
  lengthFraction: number = 0.3,
  segments: number = 8
): string | null {
  if (progress <= 0 || progress >= 1.0) return null;

  const head = Math.min(1.0, progress * (1 + lengthFraction));
  const tail = Math.max(0.0, head - lengthFraction);

  const resolvedSegments = Math.max(1, Math.round(segments));
  const step = (head - tail) / resolvedSegments;

  const points: Vec2[] = [];
  for (let i = 0; i <= resolvedSegments; i++) {
    const t = tail + step * i;
    points.push(pathFn(Math.min(1.0, Math.max(0.0, t))));
  }

  const first = points[0];
  let d = `M ${first.x} ${first.y}`;
  for (let i = 1; i < points.length; i++) {
    d += ` L ${points[i].x} ${points[i].y}`;
  }

  return d;
}
