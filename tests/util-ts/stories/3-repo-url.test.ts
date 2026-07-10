import { describe, expect, test } from '#fixtures';

type CanonicalUrlCase = [shape: string, raw: string, canonical: string];

const canonicalUrlCases: CanonicalUrlCase[] = [
  [
    'a git plus https url with a git suffix',
    'git+https://github.com/facebook/react.git',
    'https://github.com/facebook/react',
  ],
  ['a bare host and path', 'github.com/dahlia/optique', 'https://github.com/dahlia/optique'],
  ['an ssh style remote', 'git@github.com:psf/requests.git', 'https://github.com/psf/requests'],
  ['a github colon shorthand', 'github:colinhacks/zod', 'https://github.com/colinhacks/zod'],
  ['a url with extra path segments', 'https://github.com/foo/bar/tree/main/packages/x', 'https://github.com/foo/bar'],
  ['a non github host url with a git suffix', 'https://gitlab.com/owner/repo.git', 'https://gitlab.com/owner/repo'],
  ['a git plus ssh protocol remote', 'git+ssh://git@github.com/psf/requests.git', 'https://github.com/psf/requests'],
];

describe('3.1 normalizing many repo url shapes into a canonical https url', () => {
  test.for(canonicalUrlCases)(
    '3.1.1 normalizes %s into a canonical https url',
    ([, raw, canonical], { normalizeRepoUrl }) => {
      expect(normalizeRepoUrl(raw)).toBe(canonical);
    },
  );
});

const nonRepoInputCases: [shape: string, raw: string | undefined][] = [
  ['an empty string', ''],
  ['a url with no owner and repo path', 'https://example.com'],
  ['a value that is not a url', 'not a url'],
  ['an undefined input', undefined],
];

describe('3.2 rejecting values that do not name a repository', () => {
  test.for(nonRepoInputCases)('3.2.1 returns undefined for %s', ([, raw], { normalizeRepoUrl }) => {
    expect(normalizeRepoUrl(raw)).toBe(undefined);
  });
});
