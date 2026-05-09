import { test, expect } from 'vitest';
import { SessionStateStore } from '../src/session_state_store';

test('initial state', () => {
  const store = new SessionStateStore();
  expect(store.state.status).toBe('idle');
  expect(store.state.session).toBeNull();
  expect(store.state.isAuthenticated).toBe(false);
});

test('subscribe and notify', () => {
  const store = new SessionStateStore();
  let calls = 0;
  const unsub = store.subscribe(() => calls++);
  store.setStatus('loading');
  expect(calls).toBe(1);
  unsub();
  store.setStatus('ready');
  expect(calls).toBe(1); // no longer subscribed
});

test('setSession', () => {
  const store = new SessionStateStore<{id: string}>();
  store.setSession({ id: '1' });
  expect(store.state.session?.id).toBe('1');
  expect(store.state.status).toBe('ready');
  expect(store.state.isAuthenticated).toBe(true);
});

test('setError', () => {
  const store = new SessionStateStore();
  const err = new Error('test');
  store.setError(err);
  expect(store.state.status).toBe('error');
  expect(store.state.error).toBe(err);
});

test('reset', () => {
  const store = new SessionStateStore();
  store.setSession({ id: '1' });
  store.reset();
  expect(store.state.status).toBe('idle');
  expect(store.state.session).toBeNull();
});

test('runAsync success', async () => {
  const store = new SessionStateStore<string>();
  const res = await store.runAsync(Promise.resolve('ok'));
  expect(res).toBe('ok');
  expect(store.state.session).toBe('ok');
  expect(store.state.status).toBe('ready');
});

test('runAsync error', async () => {
  const store = new SessionStateStore<string>();
  await expect(store.runAsync(Promise.reject(new Error('fail')))).rejects.toThrow('fail');
  expect(store.state.status).toBe('error');
  expect(store.state.error?.message).toBe('fail');
  
  await expect(store.runAsync(Promise.reject('string error'))).rejects.toThrow('string error');
});
