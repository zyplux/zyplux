import { ensure } from '@zyplux/util/assert';
import { $, readTrimmed } from '@zyplux/util/shell';
import { parseToml } from '@zyplux/util/toml';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { compare, inc, parse } from 'semver';

import type { SurfaceFinding, Target } from './contracts.ts';

import { ManifestSchema } from './contracts.ts';
import { fetchLatestVersion } from './release-registries.ts';
import { loadReleaseSpecs, parseTargetVersion } from './release-targets.ts';

type Baseline = { label: string; version: string };
type BaseTargets = { ref: string; targets: Target[] };

const formatError = (error: unknown) => (error instanceof Error ? error.message : String(error));
const buildFinding = (status: SurfaceFinding['status'], message: string) => ({ message, status });

const validateVersion = (version: string) => {
  const parsed = parse(version);
  ensure(parsed !== null && parsed.prerelease.length === 0, `version '${version}' is not stable semver`);
  return version;
};

const loadGitFile = async (root: string, ref: string, file: string) => {
  const entry = await readTrimmed($`git ls-tree --name-only ${ref} -- ${file}`.cwd(root).quiet());
  return entry.length === 0 ? undefined : readTrimmed($`git show ${`${ref}:${file}`}`.cwd(root).quiet());
};

const loadBaseVersion = async (root: string, { ref, targets }: BaseTargets, { kind, label }: Target) => {
  const base = targets.find(candidate => candidate.label === label && candidate.kind === kind);
  if (base === undefined) return;
  const content = await loadGitFile(root, ref, base.version.file);
  ensure(content !== undefined, `version file ${base.version.file} is missing`);
  return validateVersion(parseTargetVersion(content, base.version));
};

const validateBump = (target: Target, version: string, baseline: Baseline) => {
  const order = compare(version, baseline.version);
  if (order === 0) return [];
  if (order < 0) return [buildFinding('fail', `${target.label}: version ${version} is below ${baseline.label}`)];
  const steps = [inc(baseline.version, 'patch'), inc(baseline.version, 'minor'), inc(baseline.version, 'major')];
  const [patch, minor, major] = steps;
  return [
    steps.includes(version)
      ? buildFinding('pass', `${target.label}: ${version} is ahead of ${baseline.label}`)
      : buildFinding(
          'fail',
          `${target.label}: version ${version} skips ahead of ${baseline.label} — bump one step (${patch}, ${minor}, or ${major})`,
        ),
  ];
};

const validatePublishedVersion = async (root: string, target: Target, version: string, baseline?: Baseline) => {
  let published: string | undefined;
  try {
    const latest = await fetchLatestVersion(target, path.join(root, path.dirname(target.version.file)));
    published = latest === undefined ? undefined : validateVersion(latest);
  } catch (error) {
    return [
      buildFinding('error', `${target.label}: cannot determine the latest published version: ${formatError(error)}`),
    ];
  }
  if (published === undefined)
    return baseline === undefined
      ? [buildFinding('pass', `${target.label}: not yet released`)]
      : validateBump(target, version, baseline);
  if (baseline === undefined || compare(published, baseline.version) >= 0)
    baseline = { label: `published ${published}`, version: published };
  if (compare(version, published) !== 0) return validateBump(target, version, baseline);
  const tag = `${target.tag_prefix}${published}`;
  try {
    const changed = await readTrimmed($`git diff --name-only ${tag} -- ${target.surface}`.cwd(root).quiet());
    return changed.length === 0
      ? []
      : [
          buildFinding(
            'fail',
            `${target.label}: surface changed since ${tag} but version is still ${version} — bump it (e.g. ${inc(version, 'patch')})`,
          ),
        ];
  } catch (error) {
    return [buildFinding('error', `${target.label}: cannot diff against ${tag}: ${formatError(error)}`)];
  }
};

const validateTarget = async (root: string, target: Target, base?: BaseTargets) => {
  let version: string;
  try {
    const content = await readFile(path.join(root, target.version.file), 'utf8');
    version = validateVersion(parseTargetVersion(content, target.version));
  } catch (error) {
    return [buildFinding('fail', `${target.label}: cannot read ${target.version.file}: ${formatError(error)}`)];
  }
  let baseline: Baseline | undefined;
  if (base !== undefined) {
    try {
      const baseVersion = await loadBaseVersion(root, base, target);
      if (baseVersion !== undefined) {
        if (compare(version, baseVersion) < 0)
          return [buildFinding('fail', `${target.label}: version must not decrease from ${base.ref} (${baseVersion})`)];
        baseline = { label: `${base.ref} (${baseVersion})`, version: baseVersion };
      }
    } catch (error) {
      return [
        buildFinding('error', `${target.label}: cannot compare the target branch ${base.ref}: ${formatError(error)}`),
      ];
    }
  }
  return validatePublishedVersion(root, target, version, baseline);
};

export const checkReleaseSurface = async (base?: string): Promise<SurfaceFinding[]> => {
  try {
    const root = await readTrimmed($.git.showToplevel());
    const targets = await loadReleaseSpecs(root);
    const manifest =
      base === undefined || targets.length === 0 ? undefined : await loadGitFile(root, base, 'airlock-targets.toml');
    const baseline =
      base === undefined || manifest === undefined
        ? undefined
        : { ref: base, targets: parseToml(manifest, ManifestSchema).target };
    const verdicts = await Promise.all(targets.map(target => validateTarget(root, target, baseline)));
    const findings = verdicts.flat();
    if (findings.every(finding => finding.status === 'pass'))
      findings.push(buildFinding('pass', "every published target's version tracks its surface"));
    return findings;
  } catch (error) {
    return [buildFinding('error', `cannot check release surfaces: ${formatError(error)}`)];
  }
};
