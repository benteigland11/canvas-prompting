import {
  resolveToolbarState,
  runGuard,
  reflowGuard,
  alwaysEnabled,
} from '../src/toolbar_state_resolver';
import type { ToolbarContext, ActionDefinition } from '../src/toolbar_state_resolver';

const emptyCtx: ToolbarContext = {
  selectedNodeIds: [],
  selectedNodeTypes: [],
  staleNodeIds: [],
  executingNodeIds: [],
};

function ctx(overrides: Partial<ToolbarContext> = {}): ToolbarContext {
  return { ...emptyCtx, ...overrides };
}

describe('runGuard', () => {
  test('false when nothing selected', () => {
    expect(runGuard(emptyCtx)).toBe(false);
  });

  test('false when selected node is source type', () => {
    expect(runGuard(ctx({
      selectedNodeIds: ['n1'],
      selectedNodeTypes: ['source'],
    }))).toBe(false);
  });

  test('true when selected node is action type', () => {
    expect(runGuard(ctx({
      selectedNodeIds: ['n1'],
      selectedNodeTypes: ['action'],
    }))).toBe(true);
  });

  test('true when selected node is output type', () => {
    expect(runGuard(ctx({
      selectedNodeIds: ['n1'],
      selectedNodeTypes: ['output'],
    }))).toBe(true);
  });

  test('false when all action/output nodes are executing', () => {
    expect(runGuard(ctx({
      selectedNodeIds: ['n1', 'n2'],
      selectedNodeTypes: ['action', 'output'],
      executingNodeIds: ['n1', 'n2'],
    }))).toBe(false);
  });

  test('true when at least one action/output is NOT executing', () => {
    expect(runGuard(ctx({
      selectedNodeIds: ['n1', 'n2'],
      selectedNodeTypes: ['action', 'source'],
      executingNodeIds: ['n2'],
    }))).toBe(true);
  });

  test('true with mixed types including action', () => {
    expect(runGuard(ctx({
      selectedNodeIds: ['n1', 'n2', 'n3'],
      selectedNodeTypes: ['source', 'lens', 'action'],
    }))).toBe(true);
  });
});

describe('reflowGuard', () => {
  test('false when nothing selected', () => {
    expect(reflowGuard(emptyCtx)).toBe(false);
  });

  test('false when selected nodes are not stale', () => {
    expect(reflowGuard(ctx({
      selectedNodeIds: ['n1'],
      selectedNodeTypes: ['action'],
      staleNodeIds: ['n2'],
    }))).toBe(false);
  });

  test('true when at least one selected node is stale', () => {
    expect(reflowGuard(ctx({
      selectedNodeIds: ['n1', 'n2'],
      selectedNodeTypes: ['action', 'output'],
      staleNodeIds: ['n2'],
    }))).toBe(true);
  });
});

describe('alwaysEnabled', () => {
  test('returns true regardless of context', () => {
    expect(alwaysEnabled(emptyCtx)).toBe(true);
    expect(alwaysEnabled(ctx({ selectedNodeIds: ['n1'], selectedNodeTypes: ['source'] }))).toBe(true);
  });
});

describe('resolveToolbarState', () => {
  const runAction: ActionDefinition = {
    id: 'run', label: 'Run', group: 'execution', guard: runGuard,
  };
  const reflowAction: ActionDefinition = {
    id: 'reflow', label: 'Re-flow', group: 'execution', guard: reflowGuard,
  };
  const createAction: ActionDefinition = {
    id: 'create', label: 'Create Card', group: 'creation', guard: alwaysEnabled,
  };
  const noGuardAction: ActionDefinition = {
    id: 'settings', label: 'Settings', group: 'misc',
  };

  test('all disabled when nothing selected (except always-enabled)', () => {
    const result = resolveToolbarState(
      [runAction, reflowAction, createAction],
      emptyCtx
    );
    expect(result[0].enabled).toBe(false); // run
    expect(result[0].reason).toBeDefined();
    expect(result[1].enabled).toBe(false); // reflow
    expect(result[2].enabled).toBe(true);  // create
    expect(result[2].reason).toBeUndefined();
  });

  test('run enabled when action node selected', () => {
    const result = resolveToolbarState(
      [runAction],
      ctx({ selectedNodeIds: ['n1'], selectedNodeTypes: ['action'] })
    );
    expect(result[0].enabled).toBe(true);
    expect(result[0].reason).toBeUndefined();
  });

  test('reflow enabled when stale node selected', () => {
    const result = resolveToolbarState(
      [reflowAction],
      ctx({
        selectedNodeIds: ['n1'],
        selectedNodeTypes: ['output'],
        staleNodeIds: ['n1'],
      })
    );
    expect(result[0].enabled).toBe(true);
  });

  test('actions without guard are always enabled', () => {
    const result = resolveToolbarState([noGuardAction], emptyCtx);
    expect(result[0].enabled).toBe(true);
    expect(result[0].reason).toBeUndefined();
  });

  test('preserves action reference in result', () => {
    const result = resolveToolbarState([runAction], emptyCtx);
    expect(result[0].action).toBe(runAction);
  });

  test('resolves multiple actions at once', () => {
    const result = resolveToolbarState(
      [runAction, reflowAction, createAction, noGuardAction],
      ctx({
        selectedNodeIds: ['n1'],
        selectedNodeTypes: ['action'],
        staleNodeIds: ['n1'],
      })
    );
    expect(result.map(r => r.enabled)).toEqual([true, true, true, true]);
  });

  test('custom guard is evaluated', () => {
    const customAction: ActionDefinition = {
      id: 'custom',
      label: 'Custom',
      group: 'misc',
      guard: (c) => c.selectedNodeIds.length >= 3,
    };

    const disabled = resolveToolbarState([customAction], ctx({
      selectedNodeIds: ['n1', 'n2'],
      selectedNodeTypes: ['source', 'source'],
    }));
    expect(disabled[0].enabled).toBe(false);

    const enabled = resolveToolbarState([customAction], ctx({
      selectedNodeIds: ['n1', 'n2', 'n3'],
      selectedNodeTypes: ['source', 'source', 'source'],
    }));
    expect(enabled[0].enabled).toBe(true);
  });
});
