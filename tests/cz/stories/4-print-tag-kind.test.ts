import { describe, expect, targetsTest as test } from '#fixtures';

const TAGGED_KINDS: [tag: string, kind: string][] = [
  ['util-v1.2.3', 'npm'],
  ['cerberus-v2.3.4', 'pypi'],
  ['ci-image-v3.4.5', 'ghcr'],
];

describe('4.1 classifying a tag by its release target', () => {
  test.for(TAGGED_KINDS)(
    '4.1.1 prints the registry kind of the target that owns the tag',
    async ([tag, kind], { cz, logs }) => {
      await cz.run('print-tag-kind', tag);

      expect(logs.logLines).toEqual([kind]);
    },
  );

  test('4.1.2 rejects a tag no release target owns', async ({ cz }) => {
    await expect(cz.run('print-tag-kind', 'mystery-v1.0.0')).rejects.toThrow(
      "no release target in release-targets.toml owns tag 'mystery-v1.0.0'",
    );
  });
});
