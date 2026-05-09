import { ThreadStore } from '../src/thread_store';

describe('ThreadStore', () => {
  let store: ThreadStore;

  beforeEach(() => {
    store = new ThreadStore();
  });

  test('starts empty', () => {
    expect(store.getMessages()).toEqual([]);
    expect(store.length).toBe(0);
  });

  test('addMessage creates a message with defaults', () => {
    const msg = store.addMessage('user', 'hello');
    expect(msg.role).toBe('user');
    expect(msg.content).toBe('hello');
    expect(msg.status).toBe('complete');
    expect(msg.id).toBeTruthy();
    expect(msg.createdAt).toBeGreaterThan(0);
    expect(store.length).toBe(1);
  });

  test('addMessage with custom status', () => {
    const msg = store.addMessage('assistant', '', 'streaming');
    expect(msg.status).toBe('streaming');
    expect(msg.content).toBe('');
  });

  test('addMessage with empty content defaults to empty string', () => {
    const msg = store.addMessage('user');
    expect(msg.content).toBe('');
  });

  test('getMessage returns message by ID', () => {
    const msg = store.addMessage('user', 'test');
    expect(store.getMessage(msg.id)).toEqual(msg);
  });

  test('getMessage returns undefined for unknown ID', () => {
    expect(store.getMessage('nonexistent')).toBeUndefined();
  });

  test('getLatestByRole returns the most recent message of that role', () => {
    store.addMessage('user', 'first');
    store.addMessage('assistant', 'response');
    store.addMessage('user', 'second');
    const latest = store.getLatestByRole('user');
    expect(latest?.content).toBe('second');
  });

  test('getLatestByRole returns undefined when no messages of that role', () => {
    store.addMessage('user', 'hello');
    expect(store.getLatestByRole('assistant')).toBeUndefined();
  });

  test('appendContent appends to existing message', () => {
    const msg = store.addMessage('assistant', 'hello', 'streaming');
    const updated = store.appendContent(msg.id, ' world');
    expect(updated.content).toBe('hello world');
    expect(updated.updatedAt).toBeGreaterThanOrEqual(msg.updatedAt);
  });

  test('appendContent throws for unknown ID', () => {
    expect(() => store.appendContent('unknown', 'chunk')).toThrow('Unknown message id');
  });

  test('replaceContent replaces message content', () => {
    const msg = store.addMessage('user', 'draft');
    const updated = store.replaceContent(msg.id, 'final');
    expect(updated.content).toBe('final');
    expect(store.getMessage(msg.id)?.content).toBe('final');
  });

  test('replaceContent throws for unknown ID', () => {
    expect(() => store.replaceContent('unknown', 'text')).toThrow('Unknown message id');
  });

  test('setStatus updates message status', () => {
    const msg = store.addMessage('assistant', 'streaming...', 'streaming');
    const updated = store.setStatus(msg.id, 'complete');
    expect(updated.status).toBe('complete');
  });

  test('setStatus throws for unknown ID', () => {
    expect(() => store.setStatus('unknown', 'error')).toThrow('Unknown message id');
  });

  test('clear removes all messages', () => {
    store.addMessage('user', 'a');
    store.addMessage('assistant', 'b');
    store.clear();
    expect(store.getMessages()).toEqual([]);
    expect(store.length).toBe(0);
  });

  test('subscribe notifies on addMessage', () => {
    const spy = vi.fn();
    store.subscribe(spy);
    store.addMessage('user', 'hi');
    expect(spy).toHaveBeenCalledTimes(1);
  });

  test('subscribe notifies on appendContent', () => {
    const msg = store.addMessage('assistant', '', 'streaming');
    const spy = vi.fn();
    store.subscribe(spy);
    store.appendContent(msg.id, 'chunk');
    expect(spy).toHaveBeenCalledTimes(1);
  });

  test('subscribe notifies on clear', () => {
    store.addMessage('user', 'hi');
    const spy = vi.fn();
    store.subscribe(spy);
    store.clear();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  test('unsubscribe stops notifications', () => {
    const spy = vi.fn();
    const unsub = store.subscribe(spy);
    unsub();
    store.addMessage('user', 'hi');
    expect(spy).not.toHaveBeenCalled();
  });

  test('messages are ordered by insertion', () => {
    store.addMessage('user', 'first');
    store.addMessage('assistant', 'second');
    store.addMessage('user', 'third');
    const msgs = store.getMessages();
    expect(msgs[0].content).toBe('first');
    expect(msgs[1].content).toBe('second');
    expect(msgs[2].content).toBe('third');
  });

  test('each message gets a unique ID', () => {
    const a = store.addMessage('user', 'a');
    const b = store.addMessage('user', 'b');
    expect(a.id).not.toBe(b.id);
  });

  test('getMessages returns a frozen snapshot', () => {
    store.addMessage('user', 'a');
    const msgs = store.getMessages();
    store.addMessage('user', 'b');
    // Original snapshot should still have 1 message
    expect(msgs.length).toBe(1);
  });
});
