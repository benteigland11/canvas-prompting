import { defaultTokens, tokensToCss, applyTokens } from '../src/design_tokens.js'

describe('defaultTokens', () => {
  test('exposes core groups', () => {
    expect(defaultTokens.color).toBeDefined()
    expect(defaultTokens.space).toBeDefined()
    expect(defaultTokens.radius).toBeDefined()
    expect(defaultTokens.shadow).toBeDefined()
    expect(defaultTokens.font).toBeDefined()
    expect(defaultTokens.size).toBeDefined()
  })

  test('has warm-light palette defaults', () => {
    expect(defaultTokens.color.bg).toBe('#ffffff')
    expect(defaultTokens.color.fg).toBe('#1a1a2e')
    expect(defaultTokens.color.accent).toBe('#FF9800')
  })

  test('includes display font', () => {
    expect(defaultTokens.font.display).toContain('Cardo')
  })

  test('includes status colors', () => {
    expect(defaultTokens.color.warning).toBe('#F59E0B')
    expect(defaultTokens.color.danger).toBe('#EF4444')
    expect(defaultTokens.color.success).toBe('#22C55E')
  })

  test('includes duration tokens', () => {
    expect(defaultTokens.duration.fast).toBe('120ms')
    expect(defaultTokens.duration.normal).toBe('200ms')
    expect(defaultTokens.duration.slow).toBe('350ms')
  })

  test('includes transition tokens', () => {
    expect(defaultTokens.transition.fast).toContain('120ms')
    expect(defaultTokens.transition.normal).toContain('200ms')
  })

  test('includes z-index tokens', () => {
    expect(defaultTokens.z.base).toBe('0')
    expect(defaultTokens.z.modal).toBe('200')
  })
})

describe('tokensToCss', () => {
  test('emits :root block with custom properties', () => {
    const css = tokensToCss({ color: { bg: '#fff', fg: '#000' } })
    expect(css).toContain(':root')
    expect(css).toContain('--color-bg: #fff;')
    expect(css).toContain('--color-fg: #000;')
  })

  test('honors prefix option', () => {
    const css = tokensToCss({ color: { bg: '#fff' } }, { prefix: 'app-' })
    expect(css).toContain('--app-color-bg: #fff;')
  })
})

describe('applyTokens', () => {
  beforeEach(() => {
    document.head.innerHTML = ''
    document.body.innerHTML = ''
  })

  test('injects a <style> tag with default tokens', () => {
    applyTokens()
    const style = document.getElementById('design-tokens')
    expect(style).toBeTruthy()
    expect(style.textContent).toContain('--color-bg:')
  })

  test('updates existing tag instead of creating duplicates', () => {
    applyTokens()
    applyTokens()
    expect(document.querySelectorAll('#design-tokens').length).toBe(1)
  })

  test('overrides merge over defaults', () => {
    applyTokens({ overrides: { color: { bg: '#fafafa' } } })
    const style = document.getElementById('design-tokens')
    expect(style.textContent).toContain('--color-bg: #fafafa;')
    expect(style.textContent).toContain('--color-fg:')
  })

  test('returns the merged token tree', () => {
    const tokens = applyTokens({ overrides: { color: { accent: '#ff00ff' } } })
    expect(tokens.color.accent).toBe('#ff00ff')
    expect(tokens.color.bg).toBe(defaultTokens.color.bg)
  })

  test('honors custom id', () => {
    applyTokens({ id: 'my-tokens' })
    expect(document.getElementById('my-tokens')).toBeTruthy()
  })

  test('override replaces non-object value at leaf', () => {
    const tokens = applyTokens({ overrides: { color: { bg: null } } })
    expect(tokens.color.bg).toBe(null)
  })

  test('override of an array group replaces entirely', () => {
    const css = tokensToCss({ list: { items: ['a', 'b'] } })
    expect(css).toContain('--list-items: a,b;')
  })

  test('honors prefix in applyTokens output', () => {
    applyTokens({ prefix: 'app-' })
    const style = document.getElementById('design-tokens')
    expect(style.textContent).toContain('--app-color-bg:')
  })

  test('includes new token groups in injected CSS', () => {
    applyTokens()
    const style = document.getElementById('design-tokens')
    expect(style.textContent).toContain('--duration-fast:')
    expect(style.textContent).toContain('--transition-fast:')
    expect(style.textContent).toContain('--z-base:')
    expect(style.textContent).toContain('--color-warning:')
  })
})
