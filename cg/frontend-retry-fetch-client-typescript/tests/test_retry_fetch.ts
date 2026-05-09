import { test, expect, vi } from 'vitest';
import { fetchWithRetry } from '../src/retry_fetch';

test('success on first try', async () => {
  const mockFetch = vi.fn().mockResolvedValue({ ok: true, status: 200 });
  const res = await fetchWithRetry('/api/test', {}, {}, mockFetch as any);
  expect(res.status).toBe(200);
  expect(mockFetch).toHaveBeenCalledTimes(1);
});

test('retries on 500 and succeeds', async () => {
  const mockFetch = vi.fn()
    .mockResolvedValueOnce({ ok: false, status: 500 })
    .mockResolvedValueOnce({ ok: true, status: 200 });
  
  const res = await fetchWithRetry('/api/test', {}, { baseDelayMs: 1 }, mockFetch as any);
  expect(res.status).toBe(200);
  expect(mockFetch).toHaveBeenCalledTimes(2);
});

test('fails after max retries', async () => {
  const mockFetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
  
  const res = await fetchWithRetry('/api/test', {}, { maxRetries: 2, baseDelayMs: 1 }, mockFetch as any);
  expect(res.status).toBe(500);
  
  expect(mockFetch).toHaveBeenCalledTimes(3); // 1 initial + 2 retries
});

test('throws immediately on network error without retrying if max retries is 0', async () => {
  const mockFetch = vi.fn().mockRejectedValue(new Error('Network error'));
  
  await expect(fetchWithRetry('/api/test', {}, { maxRetries: 0 }, mockFetch as any))
    .rejects.toThrow('Network error');
  
  expect(mockFetch).toHaveBeenCalledTimes(1);
});

test('respects maxDelay limit', async () => {
  const mockFetch = vi.fn()
    .mockResolvedValueOnce({ ok: false, status: 500 })
    .mockResolvedValueOnce({ ok: false, status: 500 })
    .mockResolvedValueOnce({ ok: true, status: 200 });
  
  const res = await fetchWithRetry('/api/test', {}, { baseDelayMs: 100, maxDelayMs: 10 }, mockFetch as any);
  expect(res.status).toBe(200);
});

test('uses default fetch', async () => {
  globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200 }) as any;
  const res = await fetchWithRetry('/api/test');
  expect(res.status).toBe(200);
});
