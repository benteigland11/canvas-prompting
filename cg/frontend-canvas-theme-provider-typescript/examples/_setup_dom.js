import { Window } from 'happy-dom'

const window = new Window()
globalThis.HTMLElement = window.HTMLElement
globalThis.document = window.document
