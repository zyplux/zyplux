import { loadReleaseTargets, type ReleaseTarget, resolveReleaseTag } from '@zyplux/cz/release-targets';
import path from 'node:path';
import { beforeAll, describe, expect, it } from 'vitest';

const findTarget = (targets: ReleaseTarget[], label: string) => {
  const target = targets.find(candidate => candidate.label === label);
  if (target === undefined) throw new Error(`${label} target missing from manifest`);
  return target;
};

describe('release-targets', () => {
  let targets: ReleaseTarget[];

  beforeAll(async () => {
    targets = await loadReleaseTargets();
  });

  describe('2.1 loading release targets from the manifest', () => {
    it('2.1.1 loads every target declared in the manifest', () => {
      expect(targets.map(target => target.label)).toEqual(
        expect.arrayContaining([
          '@zyplux/cz',
          '@zyplux/eslint-config',
          '@zyplux/tsconfig',
          '@zyplux/util',
          'zyplux-cerberus',
          'ghcr.io/zyplux/ci',
        ]),
      );
    });

    it('2.1.2 exposes each target kind and directory', () => {
      const util = findTarget(targets, '@zyplux/util');
      const cerberus = findTarget(targets, 'zyplux-cerberus');

      expect({
        cerberus: {
          dirEndsWithPackageDir: cerberus.dir.endsWith(path.join('apps', 'cerberus')),
          dirIsAbsolute: path.isAbsolute(cerberus.dir),
          kind: cerberus.kind,
        },
        util: {
          dirEndsWithPackageDir: util.dir.endsWith(path.join('packages', 'util')),
          dirIsAbsolute: path.isAbsolute(util.dir),
          kind: util.kind,
        },
      }).toEqual({
        cerberus: { dirEndsWithPackageDir: true, dirIsAbsolute: true, kind: 'pypi' },
        util: { dirEndsWithPackageDir: true, dirIsAbsolute: true, kind: 'npm' },
      });
    });
  });

  describe('2.2 reading a target version from its source file', () => {
    it('2.2.1 reads a version from json and regex sources', async () => {
      const versions = await Promise.all(targets.map(async target => target.readVersion()));

      expect(versions.every(version => /^\d+\.\d+\.\d+/.test(version))).toBe(true);
    });
  });

  describe('2.3 resolving a release tag to its target', () => {
    let cerberus: ReleaseTarget;
    let cerberusVersion: string;

    beforeAll(async () => {
      cerberus = findTarget(targets, 'zyplux-cerberus');
      cerberusVersion = await cerberus.readVersion();
    });

    it('2.3.1 resolves a release tag to its target and version', async () => {
      const resolved = await resolveReleaseTag(`cerberus-v${cerberusVersion}`);

      expect({ label: resolved.target.label, version: resolved.version }).toEqual({
        label: 'zyplux-cerberus',
        version: cerberusVersion,
      });
    });

    it('2.3.2 rejects a tag no target owns', async () => {
      await expect(resolveReleaseTag('mystery-v1.0.0')).rejects.toThrow();
    });

    it('2.3.3 rejects a tag whose version does not match the manifest', async () => {
      await expect(resolveReleaseTag('cerberus-v0.0.0-does-not-exist')).rejects.toThrow();
    });
  });
});
