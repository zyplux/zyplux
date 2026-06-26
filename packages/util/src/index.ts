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

export const mapWithConcurrency = async <T, R>(
  items: readonly T[],
  limit: number,
  task: (item: T, index: number) => Promise<R>,
): Promise<R[]> => {
  const results: R[] = [];
  const queue = items.entries();
  const runWorker = async () => {
    for (const [index, item] of queue) {
      results[index] = await task(item, index);
    }
  };
  const workerCount = Math.min(Math.max(1, limit), items.length);
  await Promise.all(Array.from({ length: workerCount }, runWorker));
  return results;
};

export const parseJson = <T>(text: string, schema: ZodType<T>) => schema.parse(JSON.parse(text));

export const readJson = async <T>(path: string | URL, schema: ZodType<T>) => schema.parse(await Bun.file(path).json());

export const readJsonSync = <T>(path: string | URL, schema: ZodType<T>) =>
  parseJson(readFileSync(path, 'utf8'), schema);

const toHttpsRepoUrl = (value: string) => {
  const ssh = /^git@([^:]+):(.+)$/.exec(value);
  if (ssh !== null) {
    const [, host, repoPath] = ssh;
    return `https://${host}/${repoPath}`;
  }
  const shorthand = /^github:(.+)$/i.exec(value);
  if (shorthand !== null) return `https://github.com/${shorthand[1]}`;
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(value)) return value;
  return `https://${value}`;
};

export const normalizeRepoUrl = (raw: string | undefined): string | undefined => {
  if (raw === undefined) return undefined;
  const trimmed = raw.trim().replace(/^git\+/, '');
  if (trimmed === '') return undefined;

  let parsed: URL;
  try {
    parsed = new URL(toHttpsRepoUrl(trimmed));
  } catch {
    return undefined;
  }

  const [owner, repo] = parsed.pathname.split('/').filter(segment => segment !== '');
  if (owner === undefined || repo === undefined) return undefined;
  return `https://${parsed.hostname.toLowerCase()}/${owner}/${repo.replace(/\.git$/, '')}`;
};

type HttpMethod = 'DELETE' | 'GET' | 'HEAD' | 'PATCH' | 'POST' | 'PUT';

export class FetchError extends Error {
  public readonly response: Response;

  public constructor(response: Response, options?: ErrorOptions) {
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
