/**
 * Theme provider for a spatial canvas application.
 *
 * Manages a light/dark/system mode, resolves the effective theme by
 * listening to `prefers-color-scheme`, persists the choice to a
 * configurable storage key, and applies a design-token palette to the DOM
 * via a caller-supplied `applyFn`.
 *
 * Framework-agnostic: works in any browser environment.  A thin React
 * wrapper (context + hook) is provided as a separate export.
 */

/** Allowed mode values. */
export type ThemeMode = 'light' | 'dark' | 'system';

/** The two concrete palettes a consumer must supply. */
export type ThemePalette = Record<string, Record<string, string>>;

export interface ThemeProviderOptions {
  /** Function to apply a palette to the DOM (e.g. applyTokens). */
  applyFn: (palette: ThemePalette) => void;
  /** The light palette object. */
  lightPalette: ThemePalette;
  /** The dark palette object (optional — defaults to lightPalette). */
  darkPalette?: ThemePalette;
  /** localStorage key for persisting the mode choice. */
  storageKey?: string;
  /** Initial mode — defaults to 'system'. */
  initialMode?: ThemeMode;
}

export interface ThemeProvider {
  /** Current user-chosen mode. */
  getMode: () => ThemeMode;
  /** Resolved effective theme ('light' | 'dark'). */
  getEffective: () => 'light' | 'dark';
  /** Set mode explicitly. */
  setMode: (mode: ThemeMode) => void;
  /** Cycle: light → dark → system → light. */
  toggle: () => void;
  /** Clean up the media query listener. */
  destroy: () => void;
}

/**
 * Resolve system preference.  Returns 'dark' if the OS prefers dark,
 * otherwise 'light'.  Safe for SSR (returns 'light' when matchMedia
 * is unavailable).
 */
export function resolveSystemPreference(): 'light' | 'dark' {
  if (typeof globalThis.matchMedia !== 'function') return 'light';
  return globalThis.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light';
}

function resolveEffective(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'light' || mode === 'dark') return mode;
  return resolveSystemPreference();
}

function loadMode(storageKey: string, fallback: ThemeMode): ThemeMode {
  if (typeof globalThis.localStorage === 'undefined') return fallback;
  const stored = globalThis.localStorage.getItem(storageKey);
  if (stored === 'light' || stored === 'dark' || stored === 'system') return stored;
  return fallback;
}

function persistMode(storageKey: string, mode: ThemeMode): void {
  if (typeof globalThis.localStorage === 'undefined') return;
  globalThis.localStorage.setItem(storageKey, mode);
}

/**
 * Create a theme provider instance.
 *
 * Immediately applies the resolved palette and begins listening for
 * OS-level color-scheme changes.
 */
export function createThemeProvider(options: ThemeProviderOptions): ThemeProvider {
  const {
    applyFn,
    lightPalette,
    darkPalette = lightPalette,
    storageKey = 'theme-mode',
    initialMode = 'system',
  } = options;

  let mode: ThemeMode = loadMode(storageKey, initialMode);
  let effective: 'light' | 'dark' = resolveEffective(mode);

  function apply(): void {
    effective = resolveEffective(mode);
    const palette = effective === 'dark' ? darkPalette : lightPalette;
    applyFn(palette);

    if (typeof globalThis.document !== 'undefined') {
      globalThis.document.documentElement.setAttribute('data-theme', effective);
    }
  }

  // Initial application
  apply();

  // Listen for OS preference changes (only relevant in 'system' mode)
  let mediaQuery: MediaQueryList | null = null;
  let mediaHandler: ((e: MediaQueryListEvent) => void) | null = null;

  if (typeof globalThis.matchMedia === 'function') {
    mediaQuery = globalThis.matchMedia('(prefers-color-scheme: dark)');
    mediaHandler = () => {
      if (mode === 'system') apply();
    };
    mediaQuery.addEventListener('change', mediaHandler);
  }

  return {
    getMode: () => mode,
    getEffective: () => effective,

    setMode(newMode: ThemeMode): void {
      mode = newMode;
      persistMode(storageKey, mode);
      apply();
    },

    toggle(): void {
      const cycle: ThemeMode[] = ['light', 'dark', 'system'];
      const idx = cycle.indexOf(mode);
      const next = cycle[(idx + 1) % cycle.length];
      this.setMode(next);
    },

    destroy(): void {
      if (mediaQuery && mediaHandler) {
        mediaQuery.removeEventListener('change', mediaHandler);
      }
    },
  };
}
