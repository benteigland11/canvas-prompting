import { generateGridDots, gridPatternCss } from '../src/canvas_grid_pattern';
import type { GridCamera } from '../src/canvas_grid_pattern';

function cam(overrides: Partial<GridCamera> = {}): GridCamera {
  return {
    panX: 0,
    panY: 0,
    zoom: 1,
    viewportWidth: 400,
    viewportHeight: 300,
    ...overrides,
  };
}

describe('generateGridDots', () => {
  test('produces dots at zoom=1', () => {
    const dots = generateGridDots(cam());
    expect(dots.length).toBeGreaterThan(0);
    // Each dot should have sx, sy, radius, opacity
    expect(dots[0]).toHaveProperty('sx');
    expect(dots[0]).toHaveProperty('sy');
    expect(dots[0]).toHaveProperty('radius');
    expect(dots[0]).toHaveProperty('opacity');
  });

  test('dot spacing matches baseSpacing * zoom', () => {
    const dots = generateGridDots(cam(), { baseSpacing: 40 });
    // Find two adjacent dots on the same row
    const row0 = dots.filter(d => d.sy === dots[0].sy);
    if (row0.length >= 2) {
      const gap = Math.abs(row0[1].sx - row0[0].sx);
      expect(gap).toBeCloseTo(40, 0); // baseSpacing * zoom(1)
    }
  });

  test('opacity fades below fadeZoomThreshold', () => {
    const dots = generateGridDots(cam({ zoom: 0.3 }), { fadeZoomThreshold: 0.4 });
    expect(dots.length).toBeGreaterThan(0);
    expect(dots[0].opacity).toBeLessThan(1);
    expect(dots[0].opacity).toBeCloseTo(0.3 / 0.4, 2);
  });

  test('returns empty when dots too dense (screen spacing < 4px)', () => {
    // baseSpacing=5, coarse=25, zoom=0.1 → coarse screen spacing = 2.5px < 4px
    const dots = generateGridDots(cam({ zoom: 0.1 }), {
      baseSpacing: 5,
      coarseMultiplier: 5,
      coarseZoomThreshold: 0.2,
    });
    expect(dots.length).toBe(0);
  });

  test('uses coarse grid below coarseZoomThreshold', () => {
    const opts = { baseSpacing: 20, coarseZoomThreshold: 0.2, coarseMultiplier: 5 };
    // At zoom=0.5 fine grid: spacing=20, screenSpacing=10px
    const fine = generateGridDots(cam({ zoom: 0.5 }), opts);
    // At zoom=0.15 coarse grid: spacing=100, screenSpacing=15px
    const coarse = generateGridDots(cam({ zoom: 0.15 }), opts);
    // Coarse should have fewer dots (5x spacing)
    expect(coarse.length).toBeLessThan(fine.length);
  });

  test('respects pan offset', () => {
    const noPan = generateGridDots(cam({ panX: 0 }));
    const panned = generateGridDots(cam({ panX: 7 })); // non-grid-aligned
    // With different pan, the set of visible screen positions shifts
    if (noPan.length > 0 && panned.length > 0) {
      // The screen positions for the same world dots differ by panX
      const noPanXs = new Set(noPan.map(d => d.sx));
      const pannedXs = new Set(panned.map(d => d.sx));
      // At least some screen X positions should differ
      const overlap = [...pannedXs].filter(x => noPanXs.has(x));
      expect(overlap.length).toBeLessThan(pannedXs.size);
    }
  });

  test('full opacity at zoom=1', () => {
    const dots = generateGridDots(cam({ zoom: 1 }));
    expect(dots.every(d => d.opacity === 1)).toBe(true);
  });
});

describe('gridPatternCss', () => {
  test('returns CSS properties', () => {
    const css = gridPatternCss(cam());
    expect(css).toHaveProperty('backgroundImage');
    expect(css).toHaveProperty('backgroundSize');
    expect(css).toHaveProperty('backgroundPosition');
  });

  test('backgroundImage contains radial-gradient', () => {
    const css = gridPatternCss(cam());
    expect(css.backgroundImage).toContain('radial-gradient');
  });

  test('backgroundSize reflects spacing * zoom', () => {
    const css = gridPatternCss(cam({ zoom: 2 }), { baseSpacing: 20 });
    expect(css.backgroundSize).toBe('40px 40px');
  });

  test('uses rgba for faded zoom', () => {
    const css = gridPatternCss(cam({ zoom: 0.3 }), { fadeZoomThreshold: 0.4 });
    expect(css.backgroundImage).toContain('rgba');
  });

  test('uses dotColor at full opacity', () => {
    const css = gridPatternCss(cam(), { dotColor: '#ff0000' });
    expect(css.backgroundImage).toContain('#ff0000');
  });
});
