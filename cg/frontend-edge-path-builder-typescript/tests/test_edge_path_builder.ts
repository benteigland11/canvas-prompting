import {
  buildEdgePath,
  resolvePort,
  buildArrowhead,
} from '../src/edge_path_builder';
import type { Rect, Vec2 } from '../src/edge_path_builder';

const topRect: Rect = { x: 50, y: 10, width: 100, height: 60 };
const bottomRect: Rect = { x: 60, y: 200, width: 100, height: 60 };
const leftRect: Rect = { x: 10, y: 100, width: 80, height: 50 };
const rightRect: Rect = { x: 300, y: 100, width: 80, height: 50 };

describe('resolvePort', () => {
  test('explicit top port', () => {
    const p = resolvePort(topRect, bottomRect, 'top');
    expect(p.x).toBe(100); // center x
    expect(p.y).toBe(10);  // top edge
  });

  test('explicit bottom port', () => {
    const p = resolvePort(topRect, bottomRect, 'bottom');
    expect(p.x).toBe(100);
    expect(p.y).toBe(70); // y + height
  });

  test('explicit left port', () => {
    const p = resolvePort(topRect, bottomRect, 'left');
    expect(p.x).toBe(50);
    expect(p.y).toBe(40); // center y
  });

  test('explicit right port', () => {
    const p = resolvePort(topRect, bottomRect, 'right');
    expect(p.x).toBe(150); // x + width
    expect(p.y).toBe(40);
  });

  test('auto resolves to bottom when target is below', () => {
    const p = resolvePort(topRect, bottomRect, 'auto');
    expect(p.y).toBe(70); // bottom of topRect
  });

  test('auto resolves to top when target is above', () => {
    const p = resolvePort(bottomRect, topRect, 'auto');
    expect(p.y).toBe(200); // top of bottomRect
  });

  test('auto resolves to right when target is to the right', () => {
    const p = resolvePort(leftRect, rightRect, 'auto');
    expect(p.x).toBe(90); // right edge of leftRect
  });

  test('auto resolves to left when target is to the left', () => {
    const p = resolvePort(rightRect, leftRect, 'auto');
    expect(p.x).toBe(300); // left edge of rightRect
  });
});

describe('buildArrowhead', () => {
  test('generates a closed triangle path', () => {
    const result = buildArrowhead({ x: 0, y: 0 }, { x: 100, y: 0 }, 10, Math.PI / 6);
    expect(result.path).toContain('M');
    expect(result.path).toContain('Z');
    expect(result.position).toEqual({ x: 100, y: 0 });
  });

  test('angle points from source to target', () => {
    const horiz = buildArrowhead({ x: 0, y: 0 }, { x: 100, y: 0 }, 10, Math.PI / 6);
    expect(horiz.angle).toBeCloseTo(0, 5);

    const down = buildArrowhead({ x: 0, y: 0 }, { x: 0, y: 100 }, 10, Math.PI / 6);
    expect(down.angle).toBeCloseTo(Math.PI / 2, 5);
  });
});

describe('buildEdgePath', () => {
  test('straight mode returns M..L path', () => {
    const result = buildEdgePath(topRect, bottomRect, { mode: 'straight' });
    expect(result.path).toMatch(/^M .* L .*/);
    expect(result.arrowhead.path).toContain('Z');
    expect(result.sourcePort).toBeDefined();
    expect(result.targetPort).toBeDefined();
  });

  test('bezier mode returns M..C path', () => {
    const result = buildEdgePath(topRect, bottomRect, { mode: 'bezier' });
    expect(result.path).toContain('C');
  });

  test('step mode returns multi-segment path', () => {
    const result = buildEdgePath(topRect, bottomRect, { mode: 'step' });
    // step has M + 3 L segments
    const lCount = (result.path.match(/ L /g) || []).length;
    expect(lCount).toBe(3);
  });

  test('default mode is bezier', () => {
    const result = buildEdgePath(topRect, bottomRect);
    expect(result.path).toContain('C');
  });

  test('custom arrowSize affects arrowhead path coordinates', () => {
    const small = buildEdgePath(topRect, bottomRect, { arrowSize: 4 });
    const large = buildEdgePath(topRect, bottomRect, { arrowSize: 16 });
    // Both should produce valid paths, but different coordinates
    expect(small.arrowhead.path).not.toBe(large.arrowhead.path);
  });

  test('explicit source/target ports are honored', () => {
    const result = buildEdgePath(topRect, bottomRect, {
      sourcePort: 'right',
      targetPort: 'left',
    });
    expect(result.sourcePort.x).toBe(150); // right of topRect
    expect(result.targetPort.x).toBe(60);  // left of bottomRect
  });

  test('curvature parameter affects bezier path', () => {
    const tight = buildEdgePath(topRect, bottomRect, { curvature: 0.1 });
    const loose = buildEdgePath(topRect, bottomRect, { curvature: 0.9 });
    expect(tight.path).not.toBe(loose.path);
  });

  test('works with horizontally aligned rects', () => {
    const result = buildEdgePath(leftRect, rightRect);
    expect(result.path).toBeDefined();
    expect(result.arrowhead.path).toBeDefined();
  });
});
