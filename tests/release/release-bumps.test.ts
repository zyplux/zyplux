import { type ReleaseTarget, releaseTargets } from '@zyplux/cz/release-targets';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { expect, it } from 'vitest';

type Semver = { major: number; minor: number; patch: number };

const parseSemver = (version: string) => {
  const match = /^(\d+)\.(\d+)\.(\d+)/.exec(version);
  if (match === null) return;
  const [, major, minor, patch] = match;
  if (major === undefined) return;
  if (minor === undefined) return;
  if (patch === undefined) return;
  return { major: Number(major), minor: Number(minor), patch: Number(patch) };
};

const compareSemver = (left: Semver, right: Semver) => {
  if (left.major !== right.major) return left.major < right.major ? -1 : 1;
  if (left.minor !== right.minor) return left.minor < right.minor ? -1 : 1;
  if (left.patch !== right.patch) return left.patch < right.patch ? -1 : 1;
  return 0;
};

const nextPatch = ({ major, minor, patch }: Semver) => `${major}.${minor}.${patch + 1}`;

const repoRoot = fileURLToPath(new URL('../..', import.meta.url));

const git = (args: string[]) => execFileSync('git', ['-C', repoRoot, ...args], { encoding: 'utf8' }).trim();

const findLatestRelease = (tagPrefix: string) => {
  const listed = git(['tag', '--list', `${tagPrefix}*`]);
  const tags = listed === '' ? [] : listed.split('\n');
  let latest: undefined | { semver: Semver; tag: string; version: string };
  for (const tag of tags) {
    const version = tag.slice(tagPrefix.length);
    const semver = parseSemver(version);
    if (semver !== undefined && (latest === undefined || compareSemver(semver, latest.semver) > 0)) {
      latest = { semver, tag, version };
    }
  }
  return latest;
};

const hasSurfaceChanged = (tag: string, surface: string[]) =>
  git(['diff', '--name-only', tag, 'HEAD', '--', ...surface]) !== '';

const bumpProblem = async (target: ReleaseTarget) => {
  const version = await target.readVersion();
  const current = parseSemver(version);
  if (current === undefined) return `version "${version}" is not parseable semver`;
  const latest = findLatestRelease(target.tagPrefix);
  if (latest === undefined) return;
  const order = compareSemver(current, latest.semver);
  if (order > 0) return;
  if (order < 0) return `version ${version} is below the published ${latest.version} (${latest.tag})`;
  if (hasSurfaceChanged(latest.tag, target.readSurface())) {
    return `published code changed since ${latest.tag}, but the version is still ${version} — bump it (e.g. ${nextPatch(current)})`;
  }
  return;
};

it.each(releaseTargets)('$label is version-bumped when its published code changes', async target => {
  const problem = await bumpProblem(target);
  expect(problem, `${target.label}: ${problem}`).toBeUndefined();
});
