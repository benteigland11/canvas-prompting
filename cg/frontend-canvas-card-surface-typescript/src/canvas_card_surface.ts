/**
 * Canvas Card Surface
 *
 * Generates CSS style objects for elevated card surfaces with an
 * accent-colored left border stripe.  All visual values are
 * parameterized — the function returns a plain CSSProperties-compatible
 * object so consumers can apply it however they like (inline styles,
 * CSS-in-JS, or as a reference for hand-written CSS classes).
 *
 * Designed for spatial canvas UIs where cards represent distinct node
 * types (source, action, output, etc.), each identified by an accent color.
 */

export interface CardSurfaceOptions {
  /** Accent color for the left border stripe (CSS value). */
  accentColor?: string;
  /** Background color. Defaults to white. */
  background?: string;
  /** Text color. Defaults to near-black. */
  color?: string;
  /** Border color for the remaining three sides. */
  borderColor?: string;
  /** Border radius in px or CSS value. */
  borderRadius?: string;
  /** Left stripe width in px or CSS value. */
  stripeWidth?: string;
  /** Box shadow for resting state. */
  shadow?: string;
  /** Box shadow for hover/elevated state. */
  shadowHover?: string;
  /** Padding (CSS value). */
  padding?: string;
  /** Transition shorthand. */
  transition?: string;
}

export interface CardSurfaceStyles {
  /** Resting styles for the card container. */
  base: Record<string, string>;
  /** Additional/override styles on hover. */
  hover: Record<string, string>;
}

const defaults: Required<CardSurfaceOptions> = {
  accentColor: '#FF9800',
  background: '#ffffff',
  color: '#1a1a2e',
  borderColor: '#e5e7eb',
  borderRadius: '8px',
  stripeWidth: '3px',
  shadow: '0 1px 2px rgba(0,0,0,0.05)',
  shadowHover: '0 2px 8px rgba(0,0,0,0.08)',
  padding: '1rem',
  transition: 'box-shadow 200ms cubic-bezier(0.16, 1, 0.3, 1), border-color 200ms cubic-bezier(0.16, 1, 0.3, 1)',
};

/**
 * Build style objects for a card surface.
 *
 * @param options - Visual overrides for the card appearance.
 * @returns An object with `base` and `hover` style maps.
 */
export function cardSurfaceStyles(options: CardSurfaceOptions = {}): CardSurfaceStyles {
  const o = { ...defaults, ...options };

  return {
    base: {
      background: o.background,
      color: o.color,
      borderRadius: o.borderRadius,
      borderTop: `1px solid ${o.borderColor}`,
      borderRight: `1px solid ${o.borderColor}`,
      borderBottom: `1px solid ${o.borderColor}`,
      borderLeft: `${o.stripeWidth} solid ${o.accentColor}`,
      boxShadow: o.shadow,
      padding: o.padding,
      transition: o.transition,
    },
    hover: {
      boxShadow: o.shadowHover,
    },
  };
}

/**
 * Convert a CardSurfaceStyles object to a CSS class string.
 *
 * Useful for injecting into a `<style>` tag.
 *
 * @param className - CSS class name to use.
 * @param options - Visual overrides.
 * @returns A CSS string with `.className` and `.className:hover` rules.
 */
export function cardSurfaceCss(
  className: string,
  options: CardSurfaceOptions = {},
): string {
  const styles = cardSurfaceStyles(options);
  const baseProps = Object.entries(styles.base)
    .map(([k, v]) => `  ${camelToKebab(k)}: ${v};`)
    .join('\n');
  const hoverProps = Object.entries(styles.hover)
    .map(([k, v]) => `  ${camelToKebab(k)}: ${v};`)
    .join('\n');

  return `.${className} {\n${baseProps}\n}\n\n.${className}:hover {\n${hoverProps}\n}`;
}

function camelToKebab(str: string): string {
  return str.replace(/([A-Z])/g, '-$1').toLowerCase();
}
