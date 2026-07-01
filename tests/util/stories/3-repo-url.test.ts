import { normalizeRepoUrl } from '@zyplux/util';
import { describe, expect, it } from 'vitest';

const expectNormalizesTo = (raw: string | undefined, expected: string | undefined) => {
  expect(normalizeRepoUrl(raw)).toBe(expected);
};

describe('3.1 normalizing many repo url shapes into a canonical https url', () => {
  it('3.1.1 strips a leading git plus prefix and a trailing git suffix', () => {
    expectNormalizesTo('git+https://github.com/facebook/react.git', 'https://github.com/facebook/react');
  });

  it('3.1.2 defaults a bare host and path to an https url', () => {
    expectNormalizesTo('github.com/dahlia/optique', 'https://github.com/dahlia/optique');
  });

  it('3.1.3 converts an ssh style remote to an https url', () => {
    expectNormalizesTo('git@github.com:psf/requests.git', 'https://github.com/psf/requests');
  });

  it('3.1.4 expands a github colon shorthand into a full github url', () => {
    expectNormalizesTo('github:colinhacks/zod', 'https://github.com/colinhacks/zod');
  });

  it('3.1.5 trims extra path segments down to the owner and repo', () => {
    expectNormalizesTo('https://github.com/foo/bar/tree/main/packages/x', 'https://github.com/foo/bar');
  });

  it('3.1.6 works for a non github host and strips its git suffix', () => {
    expectNormalizesTo('https://gitlab.com/owner/repo.git', 'https://gitlab.com/owner/repo');
  });
});

describe('3.2 rejecting values that do not name a repository', () => {
  it('3.2.1 returns undefined for an empty string', () => {
    expectNormalizesTo('', undefined);
  });

  it('3.2.2 returns undefined for a url with no owner and repo path', () => {
    expectNormalizesTo('https://example.com', undefined);
  });

  it('3.2.3 returns undefined for a value that is not a url', () => {
    expectNormalizesTo('not a url', undefined);
  });

  it('3.2.4 returns undefined for an undefined input', () => {
    expectNormalizesTo(undefined, undefined);
  });
});
