import { loadReleaseTargets } from '@zyplux/cz/release-targets';
import { expect, it } from 'vitest';

it('loads every target declared in release-targets.toml', async () => {
  const targets = await loadReleaseTargets();
  const labels = targets.map(target => target.label);
  expect(labels).toEqual(
    expect.arrayContaining([
      '@zyplux/eslint-config',
      '@zyplux/tsconfig',
      '@zyplux/util',
      'zyplux-cerberus',
      'ghcr.io/zyplux/ci',
    ]),
  );
});

it('reads a semver version from each target source (json and regex)', async () => {
  const targets = await loadReleaseTargets();
  const versions = await Promise.all(targets.map(async target => target.readVersion()));
  for (const version of versions) {
    expect(version).toMatch(/^\d+\.\d+\.\d+/);
  }
});

it('forms a release tag from its prefix and version', async () => {
  const targets = await loadReleaseTargets();
  const cerberus = targets.find(target => target.label === 'zyplux-cerberus');
  if (cerberus === undefined) throw new Error('cerberus target missing from manifest');
  const version = await cerberus.readVersion();
  expect(`${cerberus.tagPrefix}${version}`).toMatch(/^cerberus-v\d+\.\d+\.\d+/);
});

it('exposes each target kind and the package directory holding its version source', async () => {
  const targets = await loadReleaseTargets();

  const util = targets.find(target => target.label === '@zyplux/util');
  if (util === undefined) throw new Error('util target missing from manifest');
  expect(util.kind).toBe('npm');
  expect(util.dir).toBe('packages/util');

  const cerberus = targets.find(target => target.label === 'zyplux-cerberus');
  if (cerberus === undefined) throw new Error('cerberus target missing from manifest');
  expect(cerberus.kind).toBe('pypi');
  expect(cerberus.dir).toBe('apps/cerberus');
});
