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
