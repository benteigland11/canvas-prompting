import { resolveWireState } from '../src/wire_state_resolver';
import type { WireStateContext, WireStyleTokens } from '../src/wire_state_resolver';

describe('resolveWireState', () => {
  test('default state: subtle border color, low opacity', () => {
    const result = resolveWireState({
      isTargetStale: false,
      isSelected: false,
      isExecuting: false,
    });
    expect(result.strokeColor).toBe('var(--color-border)');
    expect(result.strokeWidth).toBe(1.5);
    expect(result.opacity).toBe(0.6);
    expect(result.cssClass).toBe('wire--default');
    expect(result.glowColor).toBeUndefined();
    expect(result.dashArray).toBeUndefined();
  });

  test('stale state: warning color with glow', () => {
    const result = resolveWireState({
      isTargetStale: true,
      isSelected: false,
      isExecuting: false,
    });
    expect(result.strokeColor).toBe('var(--color-warning)');
    expect(result.glowColor).toBe('var(--color-warning)');
    expect(result.glowRadius).toBe(6);
    expect(result.opacity).toBe(1);
    expect(result.cssClass).toBe('wire--stale');
  });

  test('selected state: accent color, wider stroke', () => {
    const result = resolveWireState({
      isTargetStale: false,
      isSelected: true,
      isExecuting: false,
    });
    expect(result.strokeColor).toBe('var(--color-accent)');
    expect(result.strokeWidth).toBe(2.5);
    expect(result.opacity).toBe(1);
    expect(result.cssClass).toBe('wire--selected');
  });

  test('executing state: dashed accent, animated', () => {
    const result = resolveWireState({
      isTargetStale: false,
      isSelected: false,
      isExecuting: true,
      executionProgress: 0.5,
    });
    expect(result.strokeColor).toBe('var(--color-accent-strong)');
    expect(result.strokeWidth).toBe(2.5);
    expect(result.dashArray).toBe('6 4');
    expect(result.dashOffset).toBe(-50);
    expect(result.cssClass).toBe('wire--executing');
  });

  test('executing takes priority over selected', () => {
    const result = resolveWireState({
      isTargetStale: false,
      isSelected: true,
      isExecuting: true,
    });
    expect(result.cssClass).toBe('wire--executing');
  });

  test('selected takes priority over stale', () => {
    const result = resolveWireState({
      isTargetStale: true,
      isSelected: true,
      isExecuting: false,
    });
    expect(result.cssClass).toBe('wire--selected');
  });

  test('executing takes priority over stale', () => {
    const result = resolveWireState({
      isTargetStale: true,
      isSelected: false,
      isExecuting: true,
    });
    expect(result.cssClass).toBe('wire--executing');
  });

  test('executionProgress defaults to 0 when not provided', () => {
    const result = resolveWireState({
      isTargetStale: false,
      isSelected: false,
      isExecuting: true,
    });
    expect(result.dashOffset).toBe(0);
  });

  test('custom tokens override defaults', () => {
    const tokens: WireStyleTokens = {
      defaultColor: '#aaa',
      selectedColor: '#ff0',
      staleColor: '#f00',
      executingColor: '#0f0',
      defaultWidth: 2,
      selectedWidth: 4,
      staleGlowRadius: 12,
    };

    const def = resolveWireState({
      isTargetStale: false,
      isSelected: false,
      isExecuting: false,
    }, tokens);
    expect(def.strokeColor).toBe('#aaa');
    expect(def.strokeWidth).toBe(2);

    const stale = resolveWireState({
      isTargetStale: true,
      isSelected: false,
      isExecuting: false,
    }, tokens);
    expect(stale.strokeColor).toBe('#f00');
    expect(stale.glowRadius).toBe(12);

    const sel = resolveWireState({
      isTargetStale: false,
      isSelected: true,
      isExecuting: false,
    }, tokens);
    expect(sel.strokeColor).toBe('#ff0');
    expect(sel.strokeWidth).toBe(4);

    const exec = resolveWireState({
      isTargetStale: false,
      isSelected: false,
      isExecuting: true,
    }, tokens);
    expect(exec.strokeColor).toBe('#0f0');
  });

  test('partial token overrides merge with defaults', () => {
    const result = resolveWireState({
      isTargetStale: false,
      isSelected: false,
      isExecuting: false,
    }, { defaultColor: '#custom' });
    expect(result.strokeColor).toBe('#custom');
    expect(result.strokeWidth).toBe(1.5); // default preserved
  });
});
