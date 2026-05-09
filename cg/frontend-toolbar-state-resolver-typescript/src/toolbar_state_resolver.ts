/**
 * Toolbar State Resolver
 *
 * Pure function that maps a set of toolbar actions and a canvas selection
 * context to resolved action states (enabled/disabled).  Framework-agnostic
 * — returns data, not DOM.
 */

export interface ToolbarContext {
  /** IDs of currently selected nodes. */
  readonly selectedNodeIds: readonly string[];
  /** Types of currently selected nodes (parallel to selectedNodeIds). */
  readonly selectedNodeTypes: readonly string[];
  /** IDs of nodes currently marked as stale. */
  readonly staleNodeIds: readonly string[];
  /** IDs of nodes currently being executed. */
  readonly executingNodeIds: readonly string[];
}

export interface ActionDefinition {
  readonly id: string;
  readonly label: string;
  readonly icon?: string;
  readonly shortcut?: string;
  readonly group: string;
  /** Optional guard function evaluated against the context. */
  readonly guard?: (context: ToolbarContext) => boolean;
}

export interface ResolvedAction {
  /** The original action definition. */
  readonly action: ActionDefinition;
  /** Whether this action is currently enabled. */
  readonly enabled: boolean;
  /** Human-readable reason why the action is disabled, if applicable. */
  readonly reason?: string;
}

/**
 * Built-in guard: requires at least one selected node of type 'action' or 'output'
 * that is not currently executing.
 */
export function runGuard(ctx: ToolbarContext): boolean {
  if (ctx.selectedNodeIds.length === 0) return false;
  const executingSet = new Set(ctx.executingNodeIds);
  for (let i = 0; i < ctx.selectedNodeIds.length; i++) {
    const type = ctx.selectedNodeTypes[i];
    const id = ctx.selectedNodeIds[i];
    if ((type === 'action' || type === 'output') && !executingSet.has(id)) {
      return true;
    }
  }
  return false;
}

/**
 * Built-in guard: requires at least one selected node that is stale.
 */
export function reflowGuard(ctx: ToolbarContext): boolean {
  if (ctx.selectedNodeIds.length === 0) return false;
  const staleSet = new Set(ctx.staleNodeIds);
  return ctx.selectedNodeIds.some(id => staleSet.has(id));
}

/**
 * Built-in guard: always enabled.
 */
export function alwaysEnabled(_ctx: ToolbarContext): boolean {
  return true;
}

/**
 * Disable reason for failed guards.
 */
function getDisableReason(action: ActionDefinition, ctx: ToolbarContext): string | undefined {
  if (ctx.selectedNodeIds.length === 0) {
    return 'No nodes selected';
  }
  return `${action.label} is not available for the current selection`;
}

/**
 * Resolve the enabled/disabled state of each action given the current context.
 *
 * For each action:
 * - If the action has a `guard` function, evaluate it against the context.
 * - If the guard returns false, the action is disabled.
 * - If no guard is present, the action is always enabled.
 *
 * @param actions - The registered actions to resolve.
 * @param context - The current canvas selection/graph state.
 * @returns An array of resolved actions with enabled/disabled and reason.
 */
export function resolveToolbarState(
  actions: readonly ActionDefinition[],
  context: ToolbarContext
): readonly ResolvedAction[] {
  return actions.map(action => {
    if (!action.guard) {
      return { action, enabled: true };
    }

    const enabled = action.guard(context);
    return {
      action,
      enabled,
      reason: enabled ? undefined : getDisableReason(action, context),
    };
  });
}
