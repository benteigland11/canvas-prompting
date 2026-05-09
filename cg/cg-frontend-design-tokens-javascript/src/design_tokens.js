/**
 * Design token system as CSS custom properties.
 *
 * Provides a warm, light-first palette inspired by the Tiger12 brand language
 * (Inter body + Cardo display, orange accent, clean white surfaces).
 * Deep-merge overrides let consumers swap individual values without losing
 * the rest of the tree.  applyTokens() injects a single <style> tag into <head>.
 */

export const defaultTokens = {
  color: {
    bg: '#ffffff',
    'bg-elevated': '#ffffff',
    'bg-sunken': '#f9fafb',
    fg: '#1a1a2e',
    'fg-muted': '#6b7280',
    'fg-subtle': '#9ca3af',
    border: '#e5e7eb',
    'border-strong': '#d1d5db',
    accent: '#FF9800',
    'accent-strong': '#F57C00',
    'accent-soft': '#FFF3E0',
    danger: '#EF4444',
    success: '#22C55E',
    warning: '#F59E0B',
  },
  space: {
    '0': '0',
    '1': '0.25rem',
    '2': '0.5rem',
    '3': '0.75rem',
    '4': '1rem',
    '6': '1.5rem',
    '8': '2rem',
    '12': '3rem',
    '16': '4rem',
    '24': '6rem',
  },
  radius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '20px',
    full: '9999px',
  },
  shadow: {
    sm: '0 1px 2px rgba(0,0,0,0.05)',
    md: '0 2px 8px rgba(0,0,0,0.08)',
    lg: '0 8px 24px rgba(0,0,0,0.12)',
    glow: '0 0 0 1px rgba(255,152,0,0.2), 0 4px 16px rgba(255,152,0,0.1)',
  },
  font: {
    sans: '"Inter", ui-sans-serif, system-ui, -apple-system, sans-serif',
    display: '"Cardo", Georgia, "Times New Roman", serif',
    mono: 'ui-monospace, Consolas, "SF Mono", monospace',
  },
  size: {
    xs: '0.75rem',
    sm: '0.875rem',
    base: '1rem',
    md: '1.0625rem',
    lg: '1.125rem',
    xl: '1.375rem',
    '2xl': '1.75rem',
    '3xl': '2.25rem',
    '4xl': '3rem',
    '5xl': '4rem',
  },
  weight: {
    regular: '400',
    medium: '500',
    semibold: '600',
    bold: '700',
  },
  leading: {
    tight: '1.15',
    snug: '1.35',
    normal: '1.55',
    relaxed: '1.7',
  },
  ease: {
    out: 'cubic-bezier(0.16, 1, 0.3, 1)',
    inOut: 'cubic-bezier(0.65, 0, 0.35, 1)',
  },
  duration: {
    fast: '120ms',
    normal: '200ms',
    slow: '350ms',
  },
  transition: {
    fast: 'all 120ms cubic-bezier(0.16, 1, 0.3, 1)',
    normal: 'all 200ms cubic-bezier(0.16, 1, 0.3, 1)',
  },
  z: {
    base: '0',
    elevated: '10',
    overlay: '100',
    modal: '200',
    toast: '300',
  },
}

function deepMerge(base, override) {
  const out = { ...base }
  for (const key of Object.keys(override || {})) {
    const a = base[key]
    const b = override[key]
    if (a && typeof a === 'object' && !Array.isArray(a) && b && typeof b === 'object') {
      out[key] = deepMerge(a, b)
    } else {
      out[key] = b
    }
  }
  return out
}

export function tokensToCss(tokens, { prefix = '' } = {}) {
  const lines = []
  for (const group of Object.keys(tokens)) {
    for (const key of Object.keys(tokens[group])) {
      lines.push(`  --${prefix}${group}-${key}: ${tokens[group][key]};`)
    }
  }
  return `:root {\n${lines.join('\n')}\n}`
}

export function applyTokens({ overrides = {}, id = 'design-tokens', prefix = '' } = {}) {
  const tokens = deepMerge(defaultTokens, overrides)
  let style = document.getElementById(id)
  if (!style) {
    style = document.createElement('style')
    style.id = id
    document.head.appendChild(style)
  }
  style.textContent = tokensToCss(tokens, { prefix })
  return tokens
}
