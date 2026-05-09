import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { applyTokens } from '../cg/cg-frontend-design-tokens-javascript/src/design_tokens.js'
import App from './App.tsx'

// Apply Tiger12 design tokens to :root
applyTokens()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
