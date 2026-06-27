import { attempt } from './result';

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

  const parsed = attempt(() => new URL(toHttpsRepoUrl(trimmed)));
  if (!parsed.ok) return undefined;

  const { hostname, pathname } = parsed.data;
  const [owner, repo] = pathname.split('/').filter(segment => segment !== '');
  if (owner === undefined || repo === undefined) return undefined;
  return `https://${hostname.toLowerCase()}/${owner}/${repo.replace(/\.git$/, '')}`;
};
