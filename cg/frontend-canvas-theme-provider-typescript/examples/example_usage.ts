import './_setup_dom.js'
import { createThemeProvider } from '../src/canvas_theme_provider.ts'

const lightPalette = {
  color: { bg: '#ffffff', fg: '#1a1a2e', accent: '#FF9800' },
}

const darkPalette = {
  color: { bg: '#0a0b10', fg: '#f0f2f8', accent: '#FFB74D' },
}

const applied: Array<Record<string, Record<string, string>>> = []

const tp = createThemeProvider({
  applyFn: (palette) => applied.push(palette),
  lightPalette,
  darkPalette,
  initialMode: 'light',
  storageKey: 'example-theme',
})

console.log('initial mode:', tp.getMode())
console.log('initial effective:', tp.getEffective())

tp.toggle()
console.log('after toggle → mode:', tp.getMode())

tp.toggle()
console.log('after toggle → mode:', tp.getMode())

tp.toggle()
console.log('after toggle → mode:', tp.getMode())

console.log('total apply calls:', applied.length)

tp.destroy()
console.log('destroyed cleanly')
