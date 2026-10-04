import { attempt } from './result.ts';

const toHttpsRepoUrl = (value: string) => {
  const ssh = /^git@([^:]+):(.+)$/.exec(value);
  if (ssh !== null) {
    const [, host, repoPath] = ssh;
    return `https://${host}/${repoPath}`;
  }
  const shorthand = /^github:(.+)$/i.exec(value);
  if (shorthand !== null) return `https://github.com/${shorthand[1]}`;
  return /^[a-z][a-z0-9+.-]*:\/\//i.test(value) ? value : `https://${value}`;
};

export const normalizeRepoUrl = (raw: string | undefined): string | undefined => {
  if (raw === undefined) return undefined;
  const trimmed = raw.trim().replace(/^git\+/, '');
  if (trimmed === '') return undefined;

  const parsed = attempt(() => new URL(toHttpsRepoUrl(trimmed)));
  if (!parsed.ok) return undefined;

  const { hostname, pathname } = parsed.data;
  const [owner, repo] = pathname.split('/').filter(segment => segment !== '');
  return owner === undefined || repo === undefined
    ? undefined
    : `https://${hostname.toLowerCase()}/${owner}/${repo.replace(/\.git$/, '')}`;
};
