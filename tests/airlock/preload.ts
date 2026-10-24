import { syncBuiltinESMExports } from 'node:module';
import { mock } from 'node:test';
import timers from 'node:timers/promises';

const endpoint = process.env['AIRLOCK_TEST_ENDPOINT'];
if (endpoint === undefined) throw new Error('AIRLOCK_TEST_ENDPOINT must name the test server');

const fetchOriginal = globalThis.fetch;
mock.method(globalThis, 'fetch', async (input: string | URL | Request, init?: RequestInit) => {
  const headers = new Headers(init?.headers);
  headers.set('x-airlock-url', input instanceof Request ? input.url : String(input));
  headers.set('x-airlock-method', init?.method ?? 'GET');
  const response = await fetchOriginal(`${endpoint}/fetch`, { headers, method: 'POST' });
  const error = response.headers.get('x-airlock-error');
  if (error !== null) {
    await response.body?.cancel();
    throw new DOMException('Request timed out', error);
  }
  return response;
});

mock.method(timers, 'setTimeout', () => Promise.resolve());
syncBuiltinESMExports();
