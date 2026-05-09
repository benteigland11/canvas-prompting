/**
 * Thread Store
 *
 * In-memory ephemeral conversation state for chat-like micro-threads.
 * Modeled after the Python conversation-thread pattern: typed immutable
 * messages with add, append (streaming), replace, set-status, and clear
 * operations.  Pure data — no DOM, no framework, no persistence.
 */

export type MessageRole = 'user' | 'assistant' | 'system';
export type MessageStatus = 'pending' | 'streaming' | 'complete' | 'error';

export interface ThreadMessage {
  readonly id: string;
  readonly role: MessageRole;
  readonly content: string;
  readonly status: MessageStatus;
  readonly createdAt: number;
  readonly updatedAt: number;
}

export type ThreadListener = () => void;

let counter = 0;
function generateId(): string {
  counter += 1;
  return `msg_${Date.now().toString(36)}_${counter.toString(36)}`;
}

/**
 * In-memory conversation thread store.
 *
 * All mutation methods return the affected message for convenience.
 * The store is observable via `subscribe()`.
 */
export class ThreadStore {
  private _messages: ThreadMessage[] = [];
  private _listeners = new Set<ThreadListener>();

  /** Current ordered list of messages. */
  getMessages(): readonly ThreadMessage[] {
    return this._messages;
  }

  /** Get a message by ID, or undefined if not found. */
  getMessage(id: string): ThreadMessage | undefined {
    return this._messages.find(m => m.id === id);
  }

  /** Get the most recent message with a given role, or undefined. */
  getLatestByRole(role: MessageRole): ThreadMessage | undefined {
    for (let i = this._messages.length - 1; i >= 0; i--) {
      if (this._messages[i].role === role) return this._messages[i];
    }
    return undefined;
  }

  /**
   * Add a new message to the thread.
   *
   * @param role - Message author role.
   * @param content - Initial content (default empty for streaming).
   * @param status - Initial status (default 'complete').
   * @returns The created message.
   */
  addMessage(
    role: MessageRole,
    content: string = '',
    status: MessageStatus = 'complete'
  ): ThreadMessage {
    const now = Date.now();
    const message: ThreadMessage = {
      id: generateId(),
      role,
      content,
      status,
      createdAt: now,
      updatedAt: now,
    };
    this._messages = [...this._messages, message];
    this._notify();
    return message;
  }

  /**
   * Append a chunk of content to an existing message (streaming use case).
   *
   * @throws If the message ID is not found.
   */
  appendContent(id: string, chunk: string): ThreadMessage {
    return this._updateMessage(id, msg => ({
      ...msg,
      content: msg.content + chunk,
      updatedAt: Date.now(),
    }));
  }

  /**
   * Replace the entire content of a message.
   *
   * @throws If the message ID is not found.
   */
  replaceContent(id: string, content: string): ThreadMessage {
    return this._updateMessage(id, msg => ({
      ...msg,
      content,
      updatedAt: Date.now(),
    }));
  }

  /**
   * Update the status of a message.
   *
   * @throws If the message ID is not found.
   */
  setStatus(id: string, status: MessageStatus): ThreadMessage {
    return this._updateMessage(id, msg => ({
      ...msg,
      status,
      updatedAt: Date.now(),
    }));
  }

  /** Remove all messages. */
  clear(): void {
    this._messages = [];
    this._notify();
  }

  /** Number of messages. */
  get length(): number {
    return this._messages.length;
  }

  /**
   * Subscribe to state changes.
   * @returns An unsubscribe function.
   */
  subscribe(listener: ThreadListener): () => void {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  private _updateMessage(
    id: string,
    updater: (msg: ThreadMessage) => ThreadMessage
  ): ThreadMessage {
    let updated: ThreadMessage | undefined;
    this._messages = this._messages.map(msg => {
      if (msg.id === id) {
        updated = updater(msg);
        return updated;
      }
      return msg;
    });
    if (!updated) throw new Error(`Unknown message id: ${id}`);
    this._notify();
    return updated;
  }

  private _notify(): void {
    for (const listener of this._listeners) {
      listener();
    }
  }
}
