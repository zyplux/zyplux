import { loadReleaseTargets, type ReleaseTarget, resolveReleaseTag } from '@zyplux/cz/release-targets';
import { fakeShellOutput } from '@zyplux/tests-shell-fixtures';
import { $ } from '@zyplux/util/shell';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

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

  describe('2.4 reading a version whose regex does not match its source file', () => {
    let dir: string;
    const originalShowToplevel = $.git.showToplevel;

    beforeEach(async () => {
      dir = await mkdtemp(path.join(tmpdir(), 'cz-release-targets-'));
      await writeFile(
        path.join(dir, 'release-targets.toml'),
        [
          '[[target]]',
          'kind = "npm"',
          'label = "broken-target"',
          'surface = []',
          'tag_prefix = "broken-v"',
          'version = { file = "VERSION", regex = \'^nomatch$\' }',
        ].join('\n'),
        'utf8',
      );
      await writeFile(path.join(dir, 'VERSION'), '1.2.3\n', 'utf8');
      $.git.showToplevel = () => Promise.resolve(fakeShellOutput(dir));
    });

    afterEach(async () => {
      $.git.showToplevel = originalShowToplevel;
      await rm(dir, { force: true, recursive: true });
    });

    it('2.4.1 rejects reading a version whose regex does not match the file', async () => {
      const [brokenTarget] = await loadReleaseTargets();
      if (brokenTarget === undefined) throw new Error('expected a target from the crafted manifest');

      await expect(brokenTarget.readVersion()).rejects.toThrow('could not read version from VERSION');
    });
  });

  describe('2.5 checking whether the ghcr image target is published', () => {
    it('2.5.1 treats a failed registry auth handshake as not published', async () => {
      vi.stubGlobal('fetch', (input: string | URL) =>
        Promise.resolve(
          String(input).includes('/token?')
            ? new Response(undefined, { status: 404 })
            : new Response(undefined, { status: 200 }),
        ),
      );
      try {
        const ci = findTarget(targets, 'ghcr.io/zyplux/ci');

        await expect(ci.isPublished('9.9.9')).resolves.toBe(false);
      } finally {
        vi.unstubAllGlobals();
      }
    });
  });
});
