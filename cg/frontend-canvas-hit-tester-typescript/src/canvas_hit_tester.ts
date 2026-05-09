/**
 * Canvas Hit Tester
 *
 * Point-in-rect and rect-intersection queries for node-based canvases.
 * Returns hit results sorted by z-index (topmost first).
 * Pure math — no DOM.
 */

export interface HitNode {
  readonly id: string;
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
  readonly zIndex?: number;
}

export interface HitResult {
  /** The ID of the hit node. */
  readonly nodeId: string;
  /** The node's bounding rectangle. */
  readonly bounds: { x: number; y: number; width: number; height: number };
  /** The node's z-index (higher = on top). */
  readonly zIndex: number;
}

/**
 * Test which nodes contain a given world-space point.
 *
 * @param point - The query point in world coordinates.
 * @param nodes - The array of positioned nodes to test against.
 * @returns Hit results sorted by z-index descending (topmost first).
 */
export function hitTestPoint(
  point: { x: number; y: number },
  nodes: readonly HitNode[]
): readonly HitResult[] {
  const hits: HitResult[] = [];

  for (const node of nodes) {
    if (
      point.x >= node.x &&
      point.x <= node.x + node.width &&
      point.y >= node.y &&
      point.y <= node.y + node.height
    ) {
      hits.push({
        nodeId: node.id,
        bounds: { x: node.x, y: node.y, width: node.width, height: node.height },
        zIndex: node.zIndex ?? 0,
      });
    }
  }

  // Sort by z-index descending (topmost first)
  hits.sort((a, b) => b.zIndex - a.zIndex);
  return hits;
}

/**
 * Test which nodes intersect a given world-space rectangle.
 * Useful for lasso/marquee selection.
 *
 * @param rect - The query rectangle in world coordinates.
 * @param nodes - The array of positioned nodes to test against.
 * @returns Hit results sorted by z-index descending (topmost first).
 */
export function hitTestRect(
  rect: { x: number; y: number; width: number; height: number },
  nodes: readonly HitNode[]
): readonly HitResult[] {
  const hits: HitResult[] = [];
  const rx2 = rect.x + rect.width;
  const ry2 = rect.y + rect.height;

  for (const node of nodes) {
    const nx2 = node.x + node.width;
    const ny2 = node.y + node.height;

    // AABB intersection test
    if (rect.x < nx2 && rx2 > node.x && rect.y < ny2 && ry2 > node.y) {
      hits.push({
        nodeId: node.id,
        bounds: { x: node.x, y: node.y, width: node.width, height: node.height },
        zIndex: node.zIndex ?? 0,
      });
    }
  }

  hits.sort((a, b) => b.zIndex - a.zIndex);
  return hits;
}

/**
 * Get the topmost node at a point, or undefined if no hit.
 */
export function hitTestTopmost(
  point: { x: number; y: number },
  nodes: readonly HitNode[]
): HitResult | undefined {
  const hits = hitTestPoint(point, nodes);
  return hits.length > 0 ? hits[0] : undefined;
}
