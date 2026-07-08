import { describe, expect, test } from '#fixtures';

const TAGGED_KINDS: [label: string, tagPrefix: string, kind: string][] = [
  ['@zyplux/util', 'util-v', 'npm'],
  ['zyplux-cerberus', 'cerberus-v', 'pypi'],
  ['ghcr.io/zyplux/ci', 'ci-image-v', 'ghcr'],
];

describe('4.1 classifying a tag by its release target', () => {
  test.for(TAGGED_KINDS)(
    '4.1.1 prints the registry kind of the target that owns the tag',
    async ([label, tagPrefix, kind], { cz, findTarget, logs }) => {
      const target = await findTarget(label);

      await cz.run('print-tag-kind', `${tagPrefix}${target.version}`);

      expect(logs.logLines).toEqual([kind]);
    },
  );

  test('4.1.2 rejects a tag no release target owns', async ({ cz }) => {
    await expect(cz.run('print-tag-kind', 'mystery-v1.0.0')).rejects.toThrow(
      "no release target in release-targets.toml owns tag 'mystery-v1.0.0'",
    );
  });
});
