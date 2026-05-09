import { hitTestPoint, hitTestRect, hitTestTopmost } from '../src/canvas_hit_tester';
import type { HitNode } from '../src/canvas_hit_tester';

const nodes: HitNode[] = [
  { id: 'a', x: 0, y: 0, width: 100, height: 80, zIndex: 0 },
  { id: 'b', x: 50, y: 50, width: 100, height: 80, zIndex: 1 },
  { id: 'c', x: 200, y: 200, width: 60, height: 60, zIndex: 2 },
];

describe('hitTestPoint', () => {
  test('returns empty for miss', () => {
    expect(hitTestPoint({ x: 500, y: 500 }, nodes)).toEqual([]);
  });

  test('hits a single node', () => {
    const hits = hitTestPoint({ x: 220, y: 220 }, nodes);
    expect(hits).toHaveLength(1);
    expect(hits[0].nodeId).toBe('c');
  });

  test('hits overlapping nodes, topmost first', () => {
    const hits = hitTestPoint({ x: 75, y: 75 }, nodes);
    expect(hits).toHaveLength(2);
    expect(hits[0].nodeId).toBe('b'); // zIndex 1
    expect(hits[1].nodeId).toBe('a'); // zIndex 0
  });

  test('includes point on boundary', () => {
    const hits = hitTestPoint({ x: 0, y: 0 }, nodes);
    expect(hits.some(h => h.nodeId === 'a')).toBe(true);
  });

  test('includes point on right/bottom edge', () => {
    const hits = hitTestPoint({ x: 100, y: 80 }, nodes);
    expect(hits.some(h => h.nodeId === 'a')).toBe(true);
  });

  test('preserves bounds in result', () => {
    const hits = hitTestPoint({ x: 220, y: 220 }, nodes);
    expect(hits[0].bounds).toEqual({ x: 200, y: 200, width: 60, height: 60 });
  });

  test('defaults zIndex to 0 when missing', () => {
    const noZ: HitNode[] = [{ id: 'x', x: 0, y: 0, width: 10, height: 10 }];
    const hits = hitTestPoint({ x: 5, y: 5 }, noZ);
    expect(hits[0].zIndex).toBe(0);
  });
});

describe('hitTestRect', () => {
  test('returns empty for non-intersecting rect', () => {
    expect(hitTestRect({ x: 500, y: 500, width: 10, height: 10 }, nodes)).toEqual([]);
  });

  test('returns nodes that intersect the rect', () => {
    const hits = hitTestRect({ x: 40, y: 40, width: 30, height: 30 }, nodes);
    expect(hits.map(h => h.nodeId).sort()).toEqual(['a', 'b']);
  });

  test('lasso selects all nodes', () => {
    const hits = hitTestRect({ x: -10, y: -10, width: 300, height: 300 }, nodes);
    expect(hits).toHaveLength(3);
  });

  test('sorted by z-index descending', () => {
    const hits = hitTestRect({ x: 0, y: 0, width: 250, height: 250 }, nodes);
    expect(hits[0].nodeId).toBe('c'); // zIndex 2
    expect(hits[1].nodeId).toBe('b'); // zIndex 1
    expect(hits[2].nodeId).toBe('a'); // zIndex 0
  });

  test('does not include adjacent-but-not-overlapping', () => {
    const hits = hitTestRect({ x: 100.1, y: 0, width: 10, height: 10 }, nodes);
    // Node 'a' ends at x=100, rect starts at x=100.1 — no overlap
    expect(hits.every(h => h.nodeId !== 'a')).toBe(true);
  });
});

describe('hitTestTopmost', () => {
  test('returns topmost node', () => {
    const hit = hitTestTopmost({ x: 75, y: 75 }, nodes);
    expect(hit?.nodeId).toBe('b');
  });

  test('returns undefined for miss', () => {
    expect(hitTestTopmost({ x: 500, y: 500 }, nodes)).toBeUndefined();
  });
});
