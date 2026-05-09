import { cardSurfaceStyles, cardSurfaceCss } from '../src/canvas_card_surface.ts'

describe('cardSurfaceStyles', () => {
  test('returns base and hover objects', () => {
    const styles = cardSurfaceStyles()
    expect(styles.base).toBeDefined()
    expect(styles.hover).toBeDefined()
  })

  test('uses default accent color', () => {
    const styles = cardSurfaceStyles()
    expect(styles.base.borderLeft).toContain('#FF9800')
  })

  test('uses default white background', () => {
    const styles = cardSurfaceStyles()
    expect(styles.base.background).toBe('#ffffff')
  })

  test('accepts accent color override', () => {
    const styles = cardSurfaceStyles({ accentColor: '#3B82F6' })
    expect(styles.base.borderLeft).toContain('#3B82F6')
  })

  test('accepts background override', () => {
    const styles = cardSurfaceStyles({ background: '#f0f0f0' })
    expect(styles.base.background).toBe('#f0f0f0')
  })

  test('accepts borderColor override', () => {
    const styles = cardSurfaceStyles({ borderColor: '#ccc' })
    expect(styles.base.borderTop).toContain('#ccc')
    expect(styles.base.borderRight).toContain('#ccc')
    expect(styles.base.borderBottom).toContain('#ccc')
  })

  test('accepts borderRadius override', () => {
    const styles = cardSurfaceStyles({ borderRadius: '16px' })
    expect(styles.base.borderRadius).toBe('16px')
  })

  test('accepts stripeWidth override', () => {
    const styles = cardSurfaceStyles({ stripeWidth: '5px' })
    expect(styles.base.borderLeft).toContain('5px')
  })

  test('accepts shadow override', () => {
    const styles = cardSurfaceStyles({ shadow: 'none' })
    expect(styles.base.boxShadow).toBe('none')
  })

  test('hover has elevated shadow', () => {
    const styles = cardSurfaceStyles()
    expect(styles.hover.boxShadow).toContain('rgba')
  })

  test('accepts padding override', () => {
    const styles = cardSurfaceStyles({ padding: '2rem' })
    expect(styles.base.padding).toBe('2rem')
  })

  test('accepts color override', () => {
    const styles = cardSurfaceStyles({ color: '#333' })
    expect(styles.base.color).toBe('#333')
  })

  test('accepts transition override', () => {
    const styles = cardSurfaceStyles({ transition: 'all 0.5s' })
    expect(styles.base.transition).toBe('all 0.5s')
  })

  test('accepts shadowHover override', () => {
    const styles = cardSurfaceStyles({ shadowHover: '0 4px 16px rgba(0,0,0,0.2)' })
    expect(styles.hover.boxShadow).toBe('0 4px 16px rgba(0,0,0,0.2)')
  })
})

describe('cardSurfaceCss', () => {
  test('generates valid CSS string with class name', () => {
    const css = cardSurfaceCss('card')
    expect(css).toContain('.card {')
    expect(css).toContain('.card:hover {')
  })

  test('includes kebab-case properties', () => {
    const css = cardSurfaceCss('card')
    expect(css).toContain('border-left:')
    expect(css).toContain('box-shadow:')
    expect(css).toContain('border-radius:')
  })

  test('honors accent color override', () => {
    const css = cardSurfaceCss('source-card', { accentColor: '#3B82F6' })
    expect(css).toContain('#3B82F6')
    expect(css).toContain('.source-card {')
  })
})
