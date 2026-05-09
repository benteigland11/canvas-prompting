import { ToolbarActionRegistry } from '../src/toolbar_action_registry';

const registry = new ToolbarActionRegistry();

// Watch for changes
registry.subscribe(() => {
  console.log(`Registry updated: ${registry.size} actions`);
});

// Register execution actions
registry.registerAll([
  {
    id: 'run',
    label: 'Run',
    icon: 'play',
    shortcut: 'Ctrl+Enter',
    group: 'execution',
    handler: (id) => console.log(`Executing action: ${id}`),
  },
  {
    id: 'reflow',
    label: 'Re-flow',
    icon: 'refresh',
    shortcut: 'Ctrl+Shift+R',
    group: 'execution',
    handler: (id) => console.log(`Executing action: ${id}`),
  },
]);

// Register creation actions
registry.register({
  id: 'create-source',
  label: 'Source Card',
  icon: 'file',
  shortcut: 'Ctrl+Shift+S',
  group: 'creation',
  handler: (id) => console.log(`Creating: ${id}`),
});

// Query
console.log('All actions:', registry.getAll().map(a => a.id));
console.log('Groups:', registry.getGroups());
console.log('Execution group:', registry.getByGroup('execution').map(a => a.id));
console.log('Shortcut Ctrl+Enter:', registry.getByShortcut('Ctrl+Enter')?.label);

// Execute an action
const run = registry.getById('run');
if (run) run.handler(run.id);
