import { buildEdgePath } from '../src/edge_path_builder';

// Two cards positioned vertically
const sourceRect = { x: 50, y: 20, width: 120, height: 60 };
const targetRect = { x: 80, y: 250, width: 120, height: 60 };

// Bezier (default)
const bezier = buildEdgePath(sourceRect, targetRect);
console.log('Bezier path:', bezier.path);
console.log('Source port:', bezier.sourcePort);
console.log('Target port:', bezier.targetPort);
console.log('Arrowhead:', bezier.arrowhead.path);

// Straight
const straight = buildEdgePath(sourceRect, targetRect, { mode: 'straight' });
console.log('Straight path:', straight.path);

// Step
const step = buildEdgePath(sourceRect, targetRect, { mode: 'step' });
console.log('Step path:', step.path);

// Custom ports
const custom = buildEdgePath(sourceRect, targetRect, {
  sourcePort: 'right',
  targetPort: 'left',
  arrowSize: 12,
});
console.log('Custom ports path:', custom.path);
