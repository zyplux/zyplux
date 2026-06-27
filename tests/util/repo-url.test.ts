import { normalizeRepoUrl } from '@zyplux/util';
import { describe, expect, it } from 'vitest';

describe('normalizeRepoUrl', () => {
  it('normalizes the many shapes a repo url takes to https://host/owner/repo', () => {
    expect(normalizeRepoUrl('git+https://github.com/facebook/react.git')).toBe('https://github.com/facebook/react');
    expect(normalizeRepoUrl('github.com/dahlia/optique')).toBe('https://github.com/dahlia/optique');
    expect(normalizeRepoUrl('git@github.com:psf/requests.git')).toBe('https://github.com/psf/requests');
    expect(normalizeRepoUrl('github:colinhacks/zod')).toBe('https://github.com/colinhacks/zod');
    expect(normalizeRepoUrl('https://github.com/foo/bar/tree/main/packages/x')).toBe('https://github.com/foo/bar');
    expect(normalizeRepoUrl('https://gitlab.com/owner/repo.git')).toBe('https://gitlab.com/owner/repo');
  });

  it('rejects values that do not name a repository', () => {
    expect(normalizeRepoUrl('')).toBeUndefined();
    expect(normalizeRepoUrl('https://example.com')).toBeUndefined();
    expect(normalizeRepoUrl('not a url')).toBeUndefined();
    expect(normalizeRepoUrl(undefined)).toBeUndefined();
  });
});
