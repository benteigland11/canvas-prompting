/**
 * Wire State Resolver
 *
 * Pure function that maps an edge's state context (stale, selected, executing)
 * to resolved visual properties (stroke, width, opacity, dash, glow).
 *
 * All default values are CSS custom property references so the consumer's
 * design token system controls the actual colors.  This widget is
 * framework-agnostic — it returns data, not DOM.
 */

export interface WireStateContext {
  /** Whether the wire's target node is stale. */
  isTargetStale: boolean;
  /** Whether this wire is currently selected. */
  isSelected: boolean;
  /** Whether an LLM execution is in-flight along this wire. */
  isExecuting: boolean;
  /** Execution progress 0..1 (only meaningful when isExecuting is true). */
  executionProgress?: number;
}

export interface WireVisualProps {
  /** CSS stroke color value. */
  strokeColor: string;
  /** Stroke width in pixels. */
  strokeWidth: number;
  /** Stroke opacity 0..1. */
  opacity: number;
  /** SVG stroke-dasharray value, or undefined for solid. */
  dashArray?: string;
  /** SVG stroke-dashoffset value for animation. */
  dashOffset?: number;
  /** CSS glow/filter color for stale state, or undefined. */
  glowColor?: string;
  /** Glow blur radius in pixels, or undefined. */
  glowRadius?: number;
  /** CSS class name to apply for animations. */
  cssClass?: string;
}

export interface WireStyleTokens {
  /** Default wire stroke color. */
  defaultColor?: string;
  /** Selected wire stroke color. */
  selectedColor?: string;
  /** Stale wire stroke color. */
  staleColor?: string;
  /** Executing wire stroke color. */
  executingColor?: string;
  /** Default stroke width. */
  defaultWidth?: number;
  /** Selected stroke width. */
  selectedWidth?: number;
  /** Stale glow blur radius. */
  staleGlowRadius?: number;
}

const DEFAULT_TOKENS: Required<WireStyleTokens> = {
  defaultColor: 'var(--color-border)',
  selectedColor: 'var(--color-accent)',
  staleColor: 'var(--color-warning)',
  executingColor: 'var(--color-accent-strong)',
  defaultWidth: 1.5,
  selectedWidth: 2.5,
  staleGlowRadius: 6,
};

/**
 * Resolve the visual properties for a wire based on its state context.
 *
 * Priority order (highest to lowest):
 * 1. Executing — animated dash + accent color
 * 2. Selected — accent color, wider stroke
 * 3. Stale — warning color + glow
 * 4. Default — subtle border color
 *
 * @param context - The current state of the wire.
 * @param tokens - Optional overrides for default style values.
 */
export function resolveWireState(
  context: WireStateContext,
  tokens: WireStyleTokens = {}
): WireVisualProps {
  const t = { ...DEFAULT_TOKENS, ...tokens };

  // Executing takes highest priority
  if (context.isExecuting) {
    return {
      strokeColor: t.executingColor,
      strokeWidth: t.selectedWidth,
      opacity: 1,
      dashArray: '6 4',
      dashOffset: context.executionProgress !== undefined
        ? -(context.executionProgress * 100)
        : 0,
      cssClass: 'wire--executing',
    };
  }

  // Selected
  if (context.isSelected) {
    return {
      strokeColor: t.selectedColor,
      strokeWidth: t.selectedWidth,
      opacity: 1,
      cssClass: 'wire--selected',
    };
  }

  // Stale
  if (context.isTargetStale) {
    return {
      strokeColor: t.staleColor,
      strokeWidth: t.defaultWidth,
      opacity: 1,
      glowColor: t.staleColor,
      glowRadius: t.staleGlowRadius,
      cssClass: 'wire--stale',
    };
  }

  // Default
  return {
    strokeColor: t.defaultColor,
    strokeWidth: t.defaultWidth,
    opacity: 0.6,
    cssClass: 'wire--default',
  };
}
