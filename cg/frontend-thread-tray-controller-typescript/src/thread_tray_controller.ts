/**
 * Thread Tray Controller
 *
 * State machine managing the lifecycle of an ephemeral micro-thread
 * panel attached to a card.  Pure logic — the caller handles DOM
 * rendering and card content mutation.
 *
 * States: closed → open → submitting → committed → closed
 */

export type TrayState = 'closed' | 'open' | 'submitting' | 'committed';

export type MessageRole = 'user' | 'assistant' | 'system';
export type MessageStatus = 'pending' | 'streaming' | 'complete' | 'error';

export interface TrayMessage {
  readonly id: string;
  readonly role: MessageRole;
  readonly content: string;
  readonly status: MessageStatus;
}

export interface CommitPayload {
  /** The card ID whose content should be replaced. */
  cardId: string;
  /** The new content extracted from the latest assistant message. */
  content: string;
}

export interface TrayStore {
  addMessage(role: MessageRole, content?: string, status?: MessageStatus): TrayMessage;
  appendContent(id: string, chunk: string): TrayMessage;
  setStatus(id: string, status: MessageStatus): TrayMessage;
  getMessages(): readonly TrayMessage[];
  getLatestByRole(role: MessageRole): TrayMessage | undefined;
  clear(): void;
}

export type TrayStoreFactory = () => TrayStore;

export interface ThreadTrayControllerOptions {
  /** Factory function to create a new thread store instance. */
  createStore: TrayStoreFactory;
}

export type TrayListener = (state: TrayState) => void;

/**
 * Thread tray lifecycle controller.
 *
 * Manages open/close/commit transitions and exposes the active
 * thread store while the tray is open.
 */
export class ThreadTrayController {
  private _state: TrayState = 'closed';
  private _cardId: string | null = null;
  private _cardContent: string | null = null;
  private _store: TrayStore | null = null;
  private _createStore: TrayStoreFactory;
  private _listeners = new Set<TrayListener>();

  constructor(options: ThreadTrayControllerOptions) {
    this._createStore = options.createStore;
  }

  /** Current tray state. */
  getState(): TrayState {
    return this._state;
  }

  /** The card ID the tray is attached to, or null if closed. */
  getCardId(): string | null {
    return this._cardId;
  }

  /** The original card content when the tray was opened. */
  getCardContent(): string | null {
    return this._cardContent;
  }

  /** The active thread store, or null if closed. */
  getStore(): TrayStore | null {
    return this._store;
  }

  /**
   * Open the tray for a specific card.
   *
   * Creates a fresh thread store and seeds it with the card's current
   * content as a system-role context message.
   *
   * @param cardId - The ID of the card to attach to.
   * @param cardContent - The card's current text content.
   * @throws If the tray is already open.
   */
  open(cardId: string, cardContent: string): void {
    if (this._state !== 'closed') {
      throw new Error(`Cannot open tray: current state is "${this._state}"`);
    }

    this._cardId = cardId;
    this._cardContent = cardContent;
    this._store = this._createStore();
    this._store.addMessage('system', cardContent, 'complete');
    this._setState('open');
  }

  /**
   * Close the tray and destroy the thread store.
   *
   * Can be called from any state.
   */
  close(): void {
    if (this._state === 'closed') return;

    if (this._store) {
      this._store.clear();
    }
    this._store = null;
    this._cardId = null;
    this._cardContent = null;
    this._setState('closed');
  }

  /**
   * Commit the latest assistant message content back to the card.
   *
   * Transitions: open → submitting → committed.
   * Returns the commit payload for the caller to apply.
   *
   * @returns The payload with cardId and extracted content.
   * @throws If no complete assistant message exists or state is invalid.
   */
  commit(): CommitPayload {
    if (this._state !== 'open') {
      throw new Error(`Cannot commit: current state is "${this._state}"`);
    }
    if (!this._store || !this._cardId) {
      throw new Error('Cannot commit: no active store or card');
    }

    const latest = this._store.getLatestByRole('assistant');
    if (!latest || latest.status !== 'complete') {
      throw new Error('Cannot commit: no complete assistant message found');
    }

    this._setState('submitting');

    const payload: CommitPayload = {
      cardId: this._cardId,
      content: latest.content,
    };

    this._setState('committed');

    // Auto-close after commit
    this.close();

    return payload;
  }

  /**
   * Subscribe to state changes.
   * @returns An unsubscribe function.
   */
  subscribe(listener: TrayListener): () => void {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  private _setState(state: TrayState): void {
    this._state = state;
    for (const listener of this._listeners) {
      listener(state);
    }
  }
}
