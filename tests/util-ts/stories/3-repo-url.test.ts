import { describe, expect, test } from '#fixtures';

describe('3. Normalizing repo URLs to a canonical form', () => {
  describe('3.1 normalizing many repo url shapes into a canonical https url', () => {
    test.for([
      [
        '3.1.1 a git plus https url with a git suffix',
        'git+https://github.com/facebook/react.git',
        'https://github.com/facebook/react',
      ],
      ['3.1.2 a bare host and path', 'github.com/dahlia/optique', 'https://github.com/dahlia/optique'],
      ['3.1.3 an ssh style remote', 'git@github.com:psf/requests.git', 'https://github.com/psf/requests'],
      ['3.1.4 a github colon shorthand', 'github:colinhacks/zod', 'https://github.com/colinhacks/zod'],
      [
        '3.1.5 a url with extra path segments',
        'https://github.com/foo/bar/tree/main/packages/x',
        'https://github.com/foo/bar',
      ],
      [
        '3.1.6 a non github host url with a git suffix',
        'https://gitlab.com/owner/repo.git',
        'https://gitlab.com/owner/repo',
      ],
      [
        '3.1.7 a git plus ssh protocol remote',
        'git+ssh://git@github.com/psf/requests.git',
        'https://github.com/psf/requests',
      ],
    ])('%s', ([, raw, canonical], { normalizeRepoUrl }) => {
      expect(normalizeRepoUrl(raw)).toBe(canonical);
    });
  });

  describe('3.2 rejecting values that do not name a repository', () => {
    test.for([
      ['3.2.1 an empty string', ''],
      ['3.2.2 a url with no owner and repo path', 'https://example.com'],
      ['3.2.3 a value that is not a url', 'not a url'],
      ['3.2.4 an undefined input', undefined],
    ])('%s', ([, raw], { normalizeRepoUrl }) => {
      expect(normalizeRepoUrl(raw)).toBe(undefined);
    });
  });
});
