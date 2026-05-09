import { getLightStreak, getCurvedStreak } from '../src/streak';
import type { PathSampler } from '../src/streak';

describe('getLightStreak', () => {
  test('returns null at progress <= 0', () => {
    expect(getLightStreak({ x: 0, y: 0 }, { x: 100, y: 100 }, 0)).toBeNull();
    expect(getLightStreak({ x: 0, y: 0 }, { x: 100, y: 100 }, -0.5)).toBeNull();
  });

  test('returns null at progress >= 1.0', () => {
    expect(getLightStreak({ x: 0, y: 0 }, { x: 100, y: 100 }, 1.0)).toBeNull();
    expect(getLightStreak({ x: 0, y: 0 }, { x: 100, y: 100 }, 1.5)).toBeNull();
  });

  test('returns a line path at mid-progress', () => {
    const p = getLightStreak({ x: 0, y: 0 }, { x: 100, y: 100 }, 0.5);
    expect(p).toContain('M');
    expect(p).toContain('L');
  });

  test('custom lengthFraction', () => {
    const p = getLightStreak({ x: 0, y: 0 }, { x: 100, y: 100 }, 0.5, 0.1);
    expect(p).not.toBeNull();
  });

  test('streak at very low progress still returns a path', () => {
    const p = getLightStreak({ x: 0, y: 0 }, { x: 100, y: 100 }, 0.01);
    expect(p).not.toBeNull();
  });
});

describe('getCurvedStreak', () => {
  const linearPath: PathSampler = (t) => ({ x: t * 100, y: t * 50 });

  test('returns null at progress extremes', () => {
    expect(getCurvedStreak(linearPath, 0)).toBeNull();
    expect(getCurvedStreak(linearPath, 1.0)).toBeNull();
  });

  test('returns a multi-segment polyline path', () => {
    const p = getCurvedStreak(linearPath, 0.5, 0.3, 4);
    expect(p).not.toBeNull();
    expect(p).toContain('M');
    // Should have multiple L segments
    const lCount = (p!.match(/L /g) || []).length;
    expect(lCount).toBeGreaterThanOrEqual(1);
  });

  test('segments parameter controls point count', () => {
    const p2 = getCurvedStreak(linearPath, 0.5, 0.3, 2);
    const p8 = getCurvedStreak(linearPath, 0.5, 0.3, 8);
    // More segments = more L commands
    const count2 = (p2!.match(/L /g) || []).length;
    const count8 = (p8!.match(/L /g) || []).length;
    expect(count8).toBeGreaterThan(count2);
  });

  test('works with a curved sampler', () => {
    const circle: PathSampler = (t) => ({
      x: Math.cos(t * Math.PI * 2) * 50,
      y: Math.sin(t * Math.PI * 2) * 50,
    });
    const p = getCurvedStreak(circle, 0.5, 0.2, 6);
    expect(p).not.toBeNull();
    expect(p).toContain('M');
  });

  test('minimum segments is 1', () => {
    const p = getCurvedStreak(linearPath, 0.5, 0.3, 0);
    expect(p).not.toBeNull();
    // At least M and one L
    expect(p).toContain('M');
    expect(p).toContain('L');
  });

  test('t values are clamped to [0, 1]', () => {
    // At extreme progress with large lengthFraction, internal t could exceed bounds
    const sampler: PathSampler = (t) => {
      // Would throw if t is out of range
      if (t < 0 || t > 1) throw new Error('t out of range');
      return { x: t, y: t };
    };
    // Should not throw
    expect(() => getCurvedStreak(sampler, 0.99, 0.5, 4)).not.toThrow();
  });
});
