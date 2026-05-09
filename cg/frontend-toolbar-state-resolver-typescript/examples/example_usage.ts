import {
  resolveToolbarState,
  runGuard,
  reflowGuard,
  alwaysEnabled,
} from '../src/toolbar_state_resolver';
import type { ActionDefinition, ToolbarContext } from '../src/toolbar_state_resolver';

// Define actions with guards
const actions: ActionDefinition[] = [
  { id: 'run', label: 'Run', group: 'execution', guard: runGuard },
  { id: 'reflow', label: 'Re-flow', group: 'execution', guard: reflowGuard },
  { id: 'create', label: 'Create Card', group: 'creation', guard: alwaysEnabled },
];

// Scenario 1: nothing selected
const empty: ToolbarContext = {
  selectedNodeIds: [],
  selectedNodeTypes: [],
  staleNodeIds: [],
  executingNodeIds: [],
};
console.log('Empty selection:');
for (const r of resolveToolbarState(actions, empty)) {
  console.log(`  ${r.action.label}: ${r.enabled ? 'enabled' : 'DISABLED'} ${r.reason ?? ''}`);
}

// Scenario 2: action node selected, stale
const staleAction: ToolbarContext = {
  selectedNodeIds: ['n1'],
  selectedNodeTypes: ['action'],
  staleNodeIds: ['n1'],
  executingNodeIds: [],
};
console.log('\nStale action selected:');
for (const r of resolveToolbarState(actions, staleAction)) {
  console.log(`  ${r.action.label}: ${r.enabled ? 'enabled' : 'DISABLED'} ${r.reason ?? ''}`);
}

// Scenario 3: source node selected (run disabled)
const sourceOnly: ToolbarContext = {
  selectedNodeIds: ['n1'],
  selectedNodeTypes: ['source'],
  staleNodeIds: [],
  executingNodeIds: [],
};
console.log('\nSource node selected:');
for (const r of resolveToolbarState(actions, sourceOnly)) {
  console.log(`  ${r.action.label}: ${r.enabled ? 'enabled' : 'DISABLED'} ${r.reason ?? ''}`);
}
