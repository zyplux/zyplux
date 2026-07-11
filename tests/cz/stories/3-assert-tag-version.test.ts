import { describe, expect, targetsTest as test } from '#fixtures';

type AssertCase = [shape: string, tag: string, expectedOutcome: 'logs' | 'throws', expectedMessage: string];

const assertCases: AssertCase[] = [
  [
    "1 logs a confirmation when the tag matches its target's declared version",
    'util-v1.2.3',
    'logs',
    '@zyplux/util 1.2.3 matches util-v1.2.3',
  ],
  [
    '2 rejects a tag no release target owns',
    'mystery-v1.0.0',
    'throws',
    "no release target in release-targets.toml owns tag 'mystery-v1.0.0'",
  ],
  [
    '3 rejects a tag whose version does not match the manifest',
    'cerberus-v0.0.0-does-not-exist',
    'throws',
    'does not match zyplux-cerberus version',
  ],
];

describe('3.1 asserting a tag against the release manifest', () => {
  test.for(assertCases)('3.1.%s', async ([, tag, expectedOutcome, expectedMessage], { cz, logs }) => {
    if (expectedOutcome === 'logs') {
      await cz.run('assert-tag-version', tag);

      expect(logs).toHaveLogged(expectedMessage);
    } else {
      await expect(cz.run('assert-tag-version', tag)).rejects.toThrow(expectedMessage);
    }
  });
});
