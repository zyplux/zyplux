import { describe, expect, test } from '#fixtures';

describe('3.1 normalizing many repo url shapes into a canonical https url', () => {
  test('3.1.1 strips a leading git plus prefix and a trailing git suffix', ({ normalizeRepoUrl }) => {
    expect(normalizeRepoUrl('git+https://github.com/facebook/react.git')).toBe('https://github.com/facebook/react');
  });

  test('3.1.2 defaults a bare host and path to an https url', ({ normalizeRepoUrl }) => {
    expect(normalizeRepoUrl('github.com/dahlia/optique')).toBe('https://github.com/dahlia/optique');
  });

  test('3.1.3 converts an ssh style remote to an https url', ({ normalizeRepoUrl }) => {
    expect(normalizeRepoUrl('git@github.com:psf/requests.git')).toBe('https://github.com/psf/requests');
  });

  test('3.1.4 expands a github colon shorthand into a full github url', ({ normalizeRepoUrl }) => {
    expect(normalizeRepoUrl('github:colinhacks/zod')).toBe('https://github.com/colinhacks/zod');
  });

  test('3.1.5 trims extra path segments down to the owner and repo', ({ normalizeRepoUrl }) => {
    expect(normalizeRepoUrl('https://github.com/foo/bar/tree/main/packages/x')).toBe('https://github.com/foo/bar');
  });

  test('3.1.6 works for a non github host and strips its git suffix', ({ normalizeRepoUrl }) => {
    expect(normalizeRepoUrl('https://gitlab.com/owner/repo.git')).toBe('https://gitlab.com/owner/repo');
  });

  test('3.1.7 normalizes a git plus ssh protocol remote to an https url', ({ normalizeRepoUrl }) => {
    expect(normalizeRepoUrl('git+ssh://git@github.com/psf/requests.git')).toBe('https://github.com/psf/requests');
  });
});

describe('3.2 rejecting values that do not name a repository', () => {
  test('3.2.1 returns undefined for an empty string', ({ normalizeRepoUrl }) => {
    expect(normalizeRepoUrl('')).toBe(undefined);
  });

  test('3.2.2 returns undefined for a url with no owner and repo path', ({ normalizeRepoUrl }) => {
    expect(normalizeRepoUrl('https://example.com')).toBe(undefined);
  });

  test('3.2.3 returns undefined for a value that is not a url', ({ normalizeRepoUrl }) => {
    expect(normalizeRepoUrl('not a url')).toBe(undefined);
  });

  test('3.2.4 returns undefined for an undefined input', ({ normalizeRepoUrl }) => {
    expect(normalizeRepoUrl(undefined)).toBe(undefined);
  });
});
