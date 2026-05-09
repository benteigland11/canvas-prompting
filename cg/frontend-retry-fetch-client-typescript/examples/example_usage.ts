import { fetchWithRetry } from '../src/retry_fetch';

try {
  const res = await fetchWithRetry('/api/todos/1', undefined, {
    maxRetries: 2,
    baseDelayMs: 100
  });
  console.log(await res.json());
} catch (e) {
  console.error(e);
}
