import { resolveWireState } from '../src/wire_state_resolver';

// Default wire
const defaultWire = resolveWireState({
  isTargetStale: false,
  isSelected: false,
  isExecuting: false,
});
console.log('Default:', JSON.stringify(defaultWire, null, 2));

// Stale wire
const staleWire = resolveWireState({
  isTargetStale: true,
  isSelected: false,
  isExecuting: false,
});
console.log('Stale:', JSON.stringify(staleWire, null, 2));

// Selected wire
const selectedWire = resolveWireState({
  isTargetStale: false,
  isSelected: true,
  isExecuting: false,
});
console.log('Selected:', JSON.stringify(selectedWire, null, 2));

// Executing wire at 75% progress
const executingWire = resolveWireState({
  isTargetStale: false,
  isSelected: false,
  isExecuting: true,
  executionProgress: 0.75,
});
console.log('Executing:', JSON.stringify(executingWire, null, 2));

// Custom tokens
const customWire = resolveWireState(
  { isTargetStale: true, isSelected: false, isExecuting: false },
  { staleColor: '#ff6600', staleGlowRadius: 10 }
);
console.log('Custom stale:', JSON.stringify(customWire, null, 2));
