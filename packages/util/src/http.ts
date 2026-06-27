import type { ZodType } from 'zod';

import type { SafeResult } from './result';

import { attemptAsync } from './result';

type HttpMethod = 'DELETE' | 'GET' | 'HEAD' | 'PATCH' | 'POST' | 'PUT';

export class FetchError extends Error {
  public readonly response: Response;

  public constructor(response: Response, options?: ErrorOptions) {
    super(`fetch ${response.url} failed: ${response.status} ${response.statusText}`, options);
    this.name = 'FetchError';
    this.response = response;
  }
}

export const httpOk = async (input: string | URL, init?: RequestInit) => {
  const response = await fetch(input, init);
  return response.ok;
};

const send = (input: string | URL, init?: RequestInit) => {
  const fetchChecked = async () => {
    const response = await fetch(input, init);
    if (!response.ok) throw new FetchError(response);
    return response;
  };
  const pending = fetchChecked();
  const json = async <T>(schema: ZodType<T>) => {
    const response = await pending;
    return schema.parse(await response.json());
  };
  return {
    json,
    response: async () => pending,
    safeJson: <T>(schema: ZodType<T>): Promise<SafeResult<T>> => attemptAsync(() => json(schema)),
    text: async () => {
      const response = await pending;
      return response.text();
    },
  };
};

const withMethod = (method: HttpMethod) => (input: string | URL, init?: RequestInit) =>
  send(input, { ...init, method });

export const http = Object.assign(send, {
  delete: withMethod('DELETE'),
  get: withMethod('GET'),
  head: withMethod('HEAD'),
  patch: withMethod('PATCH'),
  post: withMethod('POST'),
  put: withMethod('PUT'),
});

export const fetchJson = async <T>(url: string | URL, schema: ZodType<T>): Promise<T | undefined> => {
  const result = await http.get(url).safeJson(schema);
  return result.ok ? result.data : undefined;
};
