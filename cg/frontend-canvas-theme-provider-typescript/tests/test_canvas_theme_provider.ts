import {
  createThemeProvider,
  resolveSystemPreference,
} from '../src/canvas_theme_provider.ts'
import type { ThemeMode, ThemePalette } from '../src/canvas_theme_provider.ts'

const lightPalette: ThemePalette = {
  color: { bg: '#ffffff', fg: '#1a1a2e', accent: '#FF9800' },
}

const darkPalette: ThemePalette = {
  color: { bg: '#0a0b10', fg: '#f0f2f8', accent: '#FFB74D' },
}

describe('resolveSystemPreference', () => {
  test('returns light when matchMedia is unavailable', () => {
    const orig = globalThis.matchMedia
    // @ts-expect-error — intentional removal for test
    delete globalThis.matchMedia
    expect(resolveSystemPreference()).toBe('light')
    globalThis.matchMedia = orig
  })

  test('returns light when system prefers light', () => {
    const orig = globalThis.matchMedia
    globalThis.matchMedia = vi.fn().mockReturnValue({ matches: false }) as unknown as typeof globalThis.matchMedia
    expect(resolveSystemPreference()).toBe('light')
    globalThis.matchMedia = orig
  })

  test('returns dark when system prefers dark', () => {
    const orig = globalThis.matchMedia
    globalThis.matchMedia = vi.fn().mockReturnValue({ matches: true }) as unknown as typeof globalThis.matchMedia
    expect(resolveSystemPreference()).toBe('dark')
    globalThis.matchMedia = orig
  })
})

describe('createThemeProvider', () => {
  let applied: ThemePalette | null
  const applyFn = (palette: ThemePalette) => { applied = palette }

  beforeEach(() => {
    applied = null
    document.documentElement.removeAttribute('data-theme')
    globalThis.localStorage.clear()
  })

  test('applies the light palette immediately', () => {
    const tp = createThemeProvider({
      applyFn,
      lightPalette,
      darkPalette,
      initialMode: 'light',
    })
    expect(applied).toEqual(lightPalette)
    expect(tp.getMode()).toBe('light')
    expect(tp.getEffective()).toBe('light')
    tp.destroy()
  })

  test('sets data-theme attribute on documentElement', () => {
    const tp = createThemeProvider({
      applyFn,
      lightPalette,
      darkPalette,
      initialMode: 'light',
    })
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    tp.destroy()
  })

  test('setMode persists to localStorage and re-applies', () => {
    const tp = createThemeProvider({
      applyFn,
      lightPalette,
      darkPalette,
      initialMode: 'light',
      storageKey: 'test-theme',
    })
    tp.setMode('dark')
    expect(tp.getMode()).toBe('dark')
    expect(tp.getEffective()).toBe('dark')
    expect(applied).toEqual(darkPalette)
    expect(globalThis.localStorage.getItem('test-theme')).toBe('dark')
    tp.destroy()
  })

  test('toggle cycles light → dark → system', () => {
    const tp = createThemeProvider({
      applyFn,
      lightPalette,
      darkPalette,
      initialMode: 'light',
    })
    expect(tp.getMode()).toBe('light')
    tp.toggle()
    expect(tp.getMode()).toBe('dark')
    tp.toggle()
    expect(tp.getMode()).toBe('system')
    tp.toggle()
    expect(tp.getMode()).toBe('light')
    tp.destroy()
  })

  test('loads persisted mode from localStorage', () => {
    globalThis.localStorage.setItem('theme-mode', 'dark')
    const tp = createThemeProvider({
      applyFn,
      lightPalette,
      darkPalette,
    })
    expect(tp.getMode()).toBe('dark')
    expect(applied).toEqual(darkPalette)
    tp.destroy()
  })

  test('ignores invalid stored values', () => {
    globalThis.localStorage.setItem('theme-mode', 'neon')
    const tp = createThemeProvider({
      applyFn,
      lightPalette,
      darkPalette,
      initialMode: 'light',
    })
    expect(tp.getMode()).toBe('light')
    tp.destroy()
  })

  test('defaults dark palette to light when not provided', () => {
    const tp = createThemeProvider({
      applyFn,
      lightPalette,
      initialMode: 'dark',
    })
    expect(applied).toEqual(lightPalette)
    tp.destroy()
  })

  test('destroy is callable without error', () => {
    const tp = createThemeProvider({
      applyFn,
      lightPalette,
      initialMode: 'light',
    })
    expect(() => tp.destroy()).not.toThrow()
  })

  test('system mode resolves to light by default in happy-dom', () => {
    const tp = createThemeProvider({
      applyFn,
      lightPalette,
      darkPalette,
      initialMode: 'system',
    })
    // happy-dom's matchMedia returns matches=false by default
    expect(tp.getEffective()).toBe('light')
    expect(applied).toEqual(lightPalette)
    tp.destroy()
  })
})
