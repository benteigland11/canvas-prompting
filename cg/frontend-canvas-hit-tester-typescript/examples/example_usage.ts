import { hitTestPoint, hitTestRect, hitTestTopmost } from '../src/canvas_hit_tester';

const nodes = [
  { id: 'card-source', x: 50, y: 50, width: 200, height: 120, zIndex: 0 },
  { id: 'card-action', x: 150, y: 100, width: 200, height: 120, zIndex: 1 },
  { id: 'card-output', x: 400, y: 300, width: 200, height: 120, zIndex: 2 },
];

// Point hit test (click at 200, 150 — overlapping area)
const pointHits = hitTestPoint({ x: 200, y: 150 }, nodes);
console.log('Point hits:', pointHits.map(h => `${h.nodeId} (z=${h.zIndex})`));

// Topmost only
const top = hitTestTopmost({ x: 200, y: 150 }, nodes);
console.log('Topmost:', top?.nodeId);

// Lasso selection (drag a rectangle)
const lassoHits = hitTestRect({ x: 100, y: 80, width: 200, height: 100 }, nodes);
console.log('Lasso hits:', lassoHits.map(h => h.nodeId));

// Miss
const miss = hitTestPoint({ x: 700, y: 700 }, nodes);
console.log('Miss:', miss.length === 0 ? 'nothing hit' : 'unexpected hit');
