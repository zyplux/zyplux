import { vi } from 'vitest';

export type FetchFake = {
  install: () => () => void;
  on: (match: RegExp | string, reply: FetchReply) => void;
  otherwise: (reply: FetchReply) => void;
  requests: string[];
};

export type FetchReply = (url: string) => Promise<Response> | Response;

type FetchRoute = { match: RegExp | string; reply: FetchReply };

const HTTP_NOT_FOUND = 404;
const HTTP_OK = 200;

export const notFoundResponse = () => new Response(undefined, { status: HTTP_NOT_FOUND });
export const okResponse = () => new Response(undefined, { status: HTTP_OK });

const isUrlMatch = (url: string, match: RegExp | string) =>
  typeof match === 'string' ? url.startsWith(match) : match.test(url);

const getRequestUrl = (input: Request | string | URL) => {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.href;
  return input.url;
};

export const createFetchFake = (): FetchFake => {
  const requests: string[] = [];
  const routes: FetchRoute[] = [];
  let fallback: FetchReply = notFoundResponse;

  const respond = (url: string) => {
    const reply = routes.findLast(candidate => isUrlMatch(url, candidate.match))?.reply ?? fallback;
    return reply(url);
  };

  const fakeFetch = async (input: Request | string | URL) => {
    const url = getRequestUrl(input);
    requests.push(url);
    return respond(url);
  };

  return {
    install: () => {
      const original = globalThis.fetch;
      vi.stubGlobal('fetch', Object.assign(fakeFetch, { preconnect: original.preconnect }));
      return () => {
        vi.stubGlobal('fetch', original);
      };
    },
    on: (match, reply) => {
      routes.push({ match, reply });
    },
    otherwise: reply => {
      fallback = reply;
    },
    requests,
  };
};
