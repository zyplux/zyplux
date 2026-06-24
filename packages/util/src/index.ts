import type { ZodType } from 'zod';

import { readFileSync } from 'node:fs';

export const ensure: (isMet: boolean, message: string) => asserts isMet = (isMet, message) => {
  if (!isMet) {
    throw new Error(message);
  }
};

type PollOptions = { attempts: number; intervalMs: number };

export const poll = async <T>(probe: () => Promise<T | undefined>, { attempts, intervalMs }: PollOptions) => {
  for (let attempt = 0; attempt < attempts; attempt++) {
    const found = await probe();
    if (found !== undefined) {
      return found;
    }
    await Bun.sleep(intervalMs);
  }
  return;
};

export const parseJson = <T>(text: string, schema: ZodType<T>) => schema.parse(JSON.parse(text));

export const readJson = async <T>(path: string | URL, schema: ZodType<T>) => schema.parse(await Bun.file(path).json());

export const readJsonSync = <T>(path: string | URL, schema: ZodType<T>) =>
  parseJson(readFileSync(path, 'utf8'), schema);

type HttpMethod = 'DELETE' | 'GET' | 'HEAD' | 'PATCH' | 'POST' | 'PUT';

export class FetchError extends Error {
  public readonly response: Response;

  public constructor(response: Response, options: ErrorOptions) {
    super(`fetch ${response.url} failed: ${response.status} ${response.statusText}`, options);
    this.name = 'FetchError';
    this.response = response;
  }
}

const send = (input: string | URL, init?: RequestInit) => {
  const fetchChecked = async () => {
    const response = await fetch(input, init);
    if (!response.ok) throw new FetchError(response);
    return response;
  };
  const pending = fetchChecked();
  return {
    json: async <T>(schema: ZodType<T>) => {
      const response = await pending;
      return schema.parse(await response.json());
    },
    response: async () => pending,
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
