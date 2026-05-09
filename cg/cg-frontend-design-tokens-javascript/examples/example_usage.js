import './_setup_dom.js'
import { applyTokens, tokensToCss, defaultTokens } from '../src/design_tokens.js'

const tokens = applyTokens({
  overrides: {
    color: { accent: '#E65100' },
    radius: { md: '10px' },
  },
})

console.log('merged accent:', tokens.color.accent)
console.log('default bg preserved:', tokens.color.bg === defaultTokens.color.bg)
console.log('display font:', tokens.font.display)
console.log('style tag injected:', !!document.getElementById('design-tokens'))
console.log('css preview:', tokensToCss({ color: { fg: '#1a1a2e' } }))
