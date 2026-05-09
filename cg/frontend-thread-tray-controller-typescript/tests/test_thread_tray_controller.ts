import { ThreadTrayController } from '../src/thread_tray_controller';
import type { TrayStore, TrayMessage, MessageRole, MessageStatus, TrayState } from '../src/thread_tray_controller';

/** Minimal in-memory store for testing. */
function createTestStore(): TrayStore {
  let messages: TrayMessage[] = [];
  let idCounter = 0;

  return {
    addMessage(role: MessageRole, content = '', status: MessageStatus = 'complete'): TrayMessage {
      idCounter += 1;
      const msg: TrayMessage = { id: `test_${idCounter}`, role, content, status };
      messages = [...messages, msg];
      return msg;
    },
    appendContent(id: string, chunk: string): TrayMessage {
      const idx = messages.findIndex(m => m.id === id);
      if (idx === -1) throw new Error(`Unknown id: ${id}`);
      const updated = { ...messages[idx], content: messages[idx].content + chunk };
      messages = messages.map(m => m.id === id ? updated : m);
      return updated;
    },
    setStatus(id: string, status: MessageStatus): TrayMessage {
      const idx = messages.findIndex(m => m.id === id);
      if (idx === -1) throw new Error(`Unknown id: ${id}`);
      const updated = { ...messages[idx], status };
      messages = messages.map(m => m.id === id ? updated : m);
      return updated;
    },
    getMessages(): readonly TrayMessage[] {
      return messages;
    },
    getLatestByRole(role: MessageRole): TrayMessage | undefined {
      for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].role === role) return messages[i];
      }
      return undefined;
    },
    clear(): void {
      messages = [];
    },
  };
}

describe('ThreadTrayController', () => {
  let controller: ThreadTrayController;

  beforeEach(() => {
    controller = new ThreadTrayController({ createStore: createTestStore });
  });

  test('starts in closed state', () => {
    expect(controller.getState()).toBe('closed');
    expect(controller.getCardId()).toBeNull();
    expect(controller.getStore()).toBeNull();
  });

  test('open transitions to open state', () => {
    controller.open('card-1', 'Card content here');
    expect(controller.getState()).toBe('open');
    expect(controller.getCardId()).toBe('card-1');
    expect(controller.getCardContent()).toBe('Card content here');
    expect(controller.getStore()).not.toBeNull();
  });

  test('open seeds the store with a system message', () => {
    controller.open('card-1', 'Some text');
    const store = controller.getStore()!;
    const messages = store.getMessages();
    expect(messages.length).toBe(1);
    expect(messages[0].role).toBe('system');
    expect(messages[0].content).toBe('Some text');
  });

  test('open throws if already open', () => {
    controller.open('card-1', 'text');
    expect(() => controller.open('card-2', 'other')).toThrow('Cannot open tray');
  });

  test('close resets to closed state', () => {
    controller.open('card-1', 'text');
    controller.close();
    expect(controller.getState()).toBe('closed');
    expect(controller.getCardId()).toBeNull();
    expect(controller.getStore()).toBeNull();
  });

  test('close is idempotent when already closed', () => {
    expect(() => controller.close()).not.toThrow();
    expect(controller.getState()).toBe('closed');
  });

  test('commit extracts latest assistant message and auto-closes', () => {
    controller.open('card-1', 'original');
    const store = controller.getStore()!;
    store.addMessage('user', 'make it better');
    store.addMessage('assistant', 'improved version', 'complete');

    const payload = controller.commit();
    expect(payload.cardId).toBe('card-1');
    expect(payload.content).toBe('improved version');
    expect(controller.getState()).toBe('closed');
  });

  test('commit throws if no complete assistant message', () => {
    controller.open('card-1', 'text');
    const store = controller.getStore()!;
    store.addMessage('user', 'hello');
    expect(() => controller.commit()).toThrow('no complete assistant message');
  });

  test('commit throws if assistant message is still streaming', () => {
    controller.open('card-1', 'text');
    const store = controller.getStore()!;
    store.addMessage('assistant', 'partial...', 'streaming');
    expect(() => controller.commit()).toThrow('no complete assistant message');
  });

  test('commit throws from closed state', () => {
    expect(() => controller.commit()).toThrow('Cannot commit');
  });

  test('subscribe notifies on state transitions', () => {
    const states: TrayState[] = [];
    controller.subscribe(s => states.push(s));

    controller.open('card-1', 'text');
    const store = controller.getStore()!;
    store.addMessage('assistant', 'done', 'complete');
    controller.commit();

    // open → submitting → committed → closed
    expect(states).toEqual(['open', 'submitting', 'committed', 'closed']);
  });

  test('unsubscribe stops notifications', () => {
    const spy = vi.fn();
    const unsub = controller.subscribe(spy);
    unsub();
    controller.open('card-1', 'text');
    expect(spy).not.toHaveBeenCalled();
  });

  test('close clears the store', () => {
    controller.open('card-1', 'text');
    const store = controller.getStore()!;
    store.addMessage('user', 'hello');
    controller.close();
    // Store was cleared before being nulled
    expect(controller.getStore()).toBeNull();
  });

  test('commit picks the LATEST assistant message', () => {
    controller.open('card-1', 'text');
    const store = controller.getStore()!;
    store.addMessage('assistant', 'first draft', 'complete');
    store.addMessage('user', 'try again');
    store.addMessage('assistant', 'second draft', 'complete');

    const payload = controller.commit();
    expect(payload.content).toBe('second draft');
  });
});
