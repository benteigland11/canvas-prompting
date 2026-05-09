import { ToolbarActionRegistry } from '../src/toolbar_action_registry';
import type { ToolbarAction } from '../src/toolbar_action_registry';

function makeAction(id: string, overrides: Partial<ToolbarAction> = {}): ToolbarAction {
  return {
    id,
    label: overrides.label ?? id,
    group: overrides.group ?? 'default',
    handler: overrides.handler ?? (() => {}),
    icon: overrides.icon,
    shortcut: overrides.shortcut,
    guard: overrides.guard,
  };
}

describe('ToolbarActionRegistry', () => {
  let registry: ToolbarActionRegistry;

  beforeEach(() => {
    registry = new ToolbarActionRegistry();
  });

  test('starts empty', () => {
    expect(registry.getAll()).toEqual([]);
    expect(registry.size).toBe(0);
  });

  test('register adds an action', () => {
    registry.register(makeAction('run'));
    expect(registry.size).toBe(1);
    expect(registry.getById('run')?.id).toBe('run');
  });

  test('register overwrites same ID', () => {
    registry.register(makeAction('run', { label: 'Run v1' }));
    registry.register(makeAction('run', { label: 'Run v2' }));
    expect(registry.size).toBe(1);
    expect(registry.getById('run')?.label).toBe('Run v2');
  });

  test('registerAll adds multiple actions', () => {
    registry.registerAll([makeAction('a'), makeAction('b'), makeAction('c')]);
    expect(registry.size).toBe(3);
  });

  test('unregister removes an action', () => {
    registry.register(makeAction('run'));
    registry.unregister('run');
    expect(registry.size).toBe(0);
    expect(registry.getById('run')).toBeUndefined();
  });

  test('unregister is no-op for unknown ID', () => {
    expect(() => registry.unregister('nonexistent')).not.toThrow();
  });

  test('getById returns undefined for unknown ID', () => {
    expect(registry.getById('nonexistent')).toBeUndefined();
  });

  test('getAll returns actions in registration order', () => {
    registry.register(makeAction('c'));
    registry.register(makeAction('a'));
    registry.register(makeAction('b'));
    const ids = registry.getAll().map(a => a.id);
    expect(ids).toEqual(['c', 'a', 'b']);
  });

  test('getByGroup filters by group', () => {
    registry.register(makeAction('run', { group: 'execution' }));
    registry.register(makeAction('reflow', { group: 'execution' }));
    registry.register(makeAction('create', { group: 'creation' }));

    const exec = registry.getByGroup('execution');
    expect(exec.map(a => a.id)).toEqual(['run', 'reflow']);

    const create = registry.getByGroup('creation');
    expect(create.map(a => a.id)).toEqual(['create']);

    const empty = registry.getByGroup('nonexistent');
    expect(empty).toEqual([]);
  });

  test('getGroups returns distinct groups in registration order', () => {
    registry.register(makeAction('run', { group: 'execution' }));
    registry.register(makeAction('create', { group: 'creation' }));
    registry.register(makeAction('reflow', { group: 'execution' }));
    expect(registry.getGroups()).toEqual(['execution', 'creation']);
  });

  test('getByShortcut finds action by shortcut string', () => {
    registry.register(makeAction('run', { shortcut: 'Ctrl+Enter' }));
    registry.register(makeAction('create', { shortcut: 'Ctrl+Shift+N' }));
    expect(registry.getByShortcut('ctrl+enter')?.id).toBe('run');
    expect(registry.getByShortcut('Ctrl+Shift+N')?.id).toBe('create');
  });

  test('getByShortcut returns undefined when no match', () => {
    registry.register(makeAction('run', { shortcut: 'Ctrl+Enter' }));
    expect(registry.getByShortcut('Alt+X')).toBeUndefined();
  });

  test('getByShortcut skips actions without shortcuts', () => {
    registry.register(makeAction('run'));
    expect(registry.getByShortcut('Ctrl+Enter')).toBeUndefined();
  });

  test('clear removes all actions', () => {
    registry.registerAll([makeAction('a'), makeAction('b')]);
    registry.clear();
    expect(registry.size).toBe(0);
    expect(registry.getAll()).toEqual([]);
  });

  test('subscribe notifies on register', () => {
    const spy = vi.fn();
    registry.subscribe(spy);
    registry.register(makeAction('run'));
    expect(spy).toHaveBeenCalledTimes(1);
  });

  test('subscribe notifies on unregister', () => {
    registry.register(makeAction('run'));
    const spy = vi.fn();
    registry.subscribe(spy);
    registry.unregister('run');
    expect(spy).toHaveBeenCalledTimes(1);
  });

  test('subscribe notifies on clear', () => {
    registry.register(makeAction('run'));
    const spy = vi.fn();
    registry.subscribe(spy);
    registry.clear();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  test('registerAll notifies once', () => {
    const spy = vi.fn();
    registry.subscribe(spy);
    registry.registerAll([makeAction('a'), makeAction('b'), makeAction('c')]);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  test('unsubscribe stops notifications', () => {
    const spy = vi.fn();
    const unsub = registry.subscribe(spy);
    unsub();
    registry.register(makeAction('run'));
    expect(spy).not.toHaveBeenCalled();
  });

  test('handler is callable from action', () => {
    const handler = vi.fn();
    registry.register(makeAction('run', { handler }));
    const action = registry.getById('run')!;
    action.handler(action.id);
    expect(handler).toHaveBeenCalledWith('run');
  });
});
