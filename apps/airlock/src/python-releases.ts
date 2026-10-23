import { ensure } from '@zyplux/util/assert';
import { parseJson } from '@zyplux/util/json';
import { $ } from '@zyplux/util/shell';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

import type { ReleaseTarget } from './release-targets.ts';

import { PythonReleaseSchema } from './contracts.ts';

const loadPythonVersion = async ({ dir, label }: ReleaseTarget) => {
  const manifest = path.join(dir, 'package.json');
  const tracking = parseJson(await readFile(manifest, 'utf8'), PythonReleaseSchema);
  ensure(tracking.name === label, `${manifest}: expected Python release target ${label}`);
  return tracking.version;
};

export const validatePythonVersions = async (targets: ReleaseTarget[]) => {
  for (const target of targets) {
    if (path.basename(target.versionFile) !== 'pyproject.toml') continue;
    const trackingVersion = await loadPythonVersion(target);
    ensure(trackingVersion === target.version, `${target.label}: package.json and pyproject.toml versions must match`);
  }
};

export const syncPythonVersions = async (targets: ReleaseTarget[], root: string) => {
  for (const target of targets) {
    if (path.basename(target.versionFile) !== 'pyproject.toml') continue;
    const version = await loadPythonVersion(target);
    await $`uv version --package ${target.label} --frozen ${version}`.cwd(root);
  }
};
