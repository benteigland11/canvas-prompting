import { cardSurfaceStyles, cardSurfaceCss } from '../src/canvas_card_surface.ts'

// Generate style objects for different card types
const sourceCard = cardSurfaceStyles({ accentColor: '#3B82F6' })
const actionCard = cardSurfaceStyles({ accentColor: '#FF9800' })
const outputCard = cardSurfaceStyles({ accentColor: '#14B8A6' })

console.log('Source card base:', JSON.stringify(sourceCard.base, null, 2))
console.log('Action card accent:', actionCard.base.borderLeft)
console.log('Output card accent:', outputCard.base.borderLeft)

// Generate a full CSS class
const css = cardSurfaceCss('canvas-card', {
  accentColor: '#F59E0B',
  stripeWidth: '4px',
  borderRadius: '12px',
})

console.log('Generated CSS:')
console.log(css)
