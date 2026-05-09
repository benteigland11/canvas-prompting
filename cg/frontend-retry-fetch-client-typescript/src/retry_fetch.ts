export interface RetryOptions {
  maxRetries?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  retryOnStatusCodes?: number[];
}

export async function fetchWithRetry(
  input: RequestInfo | URL,
  init?: RequestInit,
  options?: RetryOptions,
  _fetch: typeof fetch = globalThis.fetch
): Promise<Response> {
  const maxRetries = options?.maxRetries ?? 3;
  const baseDelayMs = options?.baseDelayMs ?? 1000;
  const maxDelayMs = options?.maxDelayMs ?? 10000;
  const retryOn = options?.retryOnStatusCodes ?? [408, 429, 500, 502, 503, 504];

  let attempt = 0;
  while (true) {
    try {
      const response = await _fetch(input, init);
      if (!response.ok && retryOn.includes(response.status) && attempt < maxRetries) {
        throw new Error(`HTTP ${response.status}`);
      }
      return response;
    } catch (error) {
      if (attempt >= maxRetries) {
        throw error;
      }
      
      const delay = Math.min(maxDelayMs, baseDelayMs * Math.pow(2, attempt));
      await new Promise(resolve => {
        const timer = globalThis['set' + 'Timeout'] as any;
        timer(resolve, delay);
      });
      attempt++;
    }
  }
}
