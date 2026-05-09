/**
 * Toolbar Action Registry
 *
 * Typed action catalog for toolbar/command bar UIs.  Actions declare
 * an id, label, optional icon, optional keyboard shortcut, group,
 * and handler.  The registry stores, queries, and observes the catalog.
 * Pure data — no DOM, no keyboard listening, no framework.
 */

export interface ToolbarAction {
  /** Unique action identifier (e.g. 'run', 'reflow', 'create-source'). */
  readonly id: string;
  /** Human-readable label (e.g. 'Run'). */
  readonly label: string;
  /** Optional icon identifier (e.g. 'play', 'refresh', 'plus'). */
  readonly icon?: string;
  /**
   * Optional keyboard shortcut declaration (e.g. 'Ctrl+Enter', 'Ctrl+Shift+N').
   * The registry stores this but does NOT listen for keyboard events —
   * the consumer wires the DOM listener.
   */
  readonly shortcut?: string;
  /** Action group for visual grouping (e.g. 'execution', 'creation'). */
  readonly group: string;
  /** The action handler.  Receives the action ID for context. */
  readonly handler: (actionId: string) => void;
  /**
   * Optional guard function.  When provided, the consumer can evaluate
   * this against a context to determine if the action should be enabled.
   * The registry stores it; the state resolver evaluates it.
   */
  readonly guard?: (context: unknown) => boolean;
}

export type RegistryListener = () => void;

/**
 * In-memory toolbar action catalog.
 */
export class ToolbarActionRegistry {
  private _actions = new Map<string, ToolbarAction>();
  private _insertionOrder: string[] = [];
  private _listeners = new Set<RegistryListener>();

  /**
   * Register a new action.  Overwrites if an action with the same ID
   * already exists.
   */
  register(action: ToolbarAction): void {
    if (!this._actions.has(action.id)) {
      this._insertionOrder.push(action.id);
    }
    this._actions.set(action.id, action);
    this._notify();
  }

  /** Register multiple actions at once. */
  registerAll(actions: readonly ToolbarAction[]): void {
    for (const action of actions) {
      if (!this._actions.has(action.id)) {
        this._insertionOrder.push(action.id);
      }
      this._actions.set(action.id, action);
    }
    this._notify();
  }

  /** Remove an action by ID.  No-op if not found. */
  unregister(id: string): void {
    if (this._actions.delete(id)) {
      this._insertionOrder = this._insertionOrder.filter(i => i !== id);
      this._notify();
    }
  }

  /** Get an action by ID, or undefined. */
  getById(id: string): ToolbarAction | undefined {
    return this._actions.get(id);
  }

  /** Get all actions in registration order. */
  getAll(): readonly ToolbarAction[] {
    return this._insertionOrder
      .map(id => this._actions.get(id)!)
      .filter(Boolean);
  }

  /** Get all actions in a group, in registration order. */
  getByGroup(group: string): readonly ToolbarAction[] {
    return this.getAll().filter(a => a.group === group);
  }

  /** Get all distinct group names in registration order. */
  getGroups(): readonly string[] {
    const seen = new Set<string>();
    const groups: string[] = [];
    for (const id of this._insertionOrder) {
      const action = this._actions.get(id);
      if (action && !seen.has(action.group)) {
        seen.add(action.group);
        groups.push(action.group);
      }
    }
    return groups;
  }

  /** Find an action by its shortcut string, or undefined. */
  getByShortcut(shortcut: string): ToolbarAction | undefined {
    const normalized = shortcut.toLowerCase();
    for (const action of this._actions.values()) {
      if (action.shortcut && action.shortcut.toLowerCase() === normalized) {
        return action;
      }
    }
    return undefined;
  }

  /** Number of registered actions. */
  get size(): number {
    return this._actions.size;
  }

  /** Remove all actions. */
  clear(): void {
    this._actions.clear();
    this._insertionOrder = [];
    this._notify();
  }

  /**
   * Subscribe to registry changes.
   * @returns An unsubscribe function.
   */
  subscribe(listener: RegistryListener): () => void {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  private _notify(): void {
    for (const listener of this._listeners) {
      listener();
    }
  }
}
