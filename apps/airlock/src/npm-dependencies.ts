import { ensure } from '@zyplux/util/assert';
import { parseJson } from '@zyplux/util/json';
import { poll } from '@zyplux/util/poll';
import { $, readTrimmed } from '@zyplux/util/shell';
import path from 'node:path';
import { satisfies, validRange } from 'semver';

import type { ReleaseTarget } from './release-targets.ts';

import { NpmArchiveSchema, WorkspacePackagesSchema } from './contracts.ts';
import { isNpmVersionAvailable } from './release-registries.ts';
import { loadReleaseTargets } from './release-targets.ts';

const DEPENDENCY_POLL_ATTEMPTS = 61;
const DEPENDENCY_POLL_INTERVAL_MS = 10_000;

const parseDependency = (name: string, specifier: string) => {
  if (!specifier.startsWith('npm:')) return { name, range: specifier };
  const packageSpec = specifier.slice('npm:'.length);
  if (validRange(packageSpec) !== null) return { name, range: packageSpec };
  const versionIndex = packageSpec.lastIndexOf('@');
  return versionIndex > 0
    ? { name: packageSpec.slice(0, versionIndex), range: packageSpec.slice(versionIndex + 1) }
    : { name: packageSpec, range: '*' };
};

export const loadNpmDependencies = async ({ label, version }: ReleaseTarget, archive: string) => {
  const manifest = parseJson(await readTrimmed($`tar -xOf ${archive} package/package.json`), NpmArchiveSchema);
  ensure(
    manifest.name === label && manifest.version === version,
    `${label}: packed package identity must match ${label}@${version}`,
  );
  const bundled = manifest.bundledDependencies ?? manifest.bundleDependencies;
  const bundledNames = new Set(
    bundled === true ? Object.keys(manifest.dependencies) : Array.isArray(bundled) ? bundled : [],
  );
  const requirements = Object.entries({ ...manifest.dependencies, ...manifest.optionalDependencies })
    .filter(([name]) => !bundledNames.has(name))
    .map(([name, specifier]) => parseDependency(name, specifier));
  if (requirements.length === 0) return [];
  const root = await readTrimmed($.git.showToplevel());
  const configuredTargets = await loadReleaseTargets();
  const configured = configuredTargets.filter(target => target.kind === 'npm');
  const workspaces = parseJson(
    await readTrimmed($`pnpm list --recursive --depth -1 --json`.cwd(root)),
    WorkspacePackagesSchema,
  );
  return workspaces
    .filter(workspace =>
      requirements.some(
        ({ name, range }) =>
          workspace.name === name && workspace.version !== undefined && satisfies(workspace.version, range),
      ),
    )
    .map(workspace => {
      const dependency = configured.find(candidate => candidate.dir === path.resolve(workspace.path));
      ensure(dependency !== undefined, `${label}: declare an npm target for dependency ${workspace.path}`);
      ensure(!workspace.private, `${label}: workspace dependency ${workspace.name} is private`);
      ensure(
        workspace.name === dependency.label && workspace.version === dependency.version,
        `${label}: dependency ${dependency.label} must match its configured name and version`,
      );
      ensure(dependency.label !== label, `${label}: cyclic production workspace dependency`);
      return dependency;
    });
};

export const orderNpmTargets = (targets: ReleaseTarget[], dependencies: ReadonlyMap<string, ReleaseTarget[]>) => {
  const pending = new Map(targets.map(target => [target.label, target]));
  const ordered: ReleaseTarget[] = [];
  const visited = new Set<string>();
  const visiting = new Set<string>();
  const visit = (target: ReleaseTarget): void => {
    if (visited.has(target.label)) return;
    ensure(!visiting.has(target.label), `${target.label}: cyclic production workspace dependency`);
    visiting.add(target.label);
    const required = dependencies.get(target.label) ?? [];
    for (const dependency of required) {
      const selected = pending.get(dependency.label);
      if (selected !== undefined) visit(selected);
    }
    visiting.delete(target.label);
    visited.add(target.label);
    ordered.push(target);
  };
  for (const target of targets) visit(target);
  return ordered;
};

export const waitForNpmDependencies = async (dependencies: ReleaseTarget[]) => {
  let pending = dependencies;
  if (pending.length === 0) return;
  console.log(`Waiting for npm dependencies: ${pending.map(target => `${target.label}@${target.version}`).join(', ')}`);
  await poll(
    async () => {
      const unavailable = await Promise.all(
        pending.map(async target => {
          const isAvailable = await isNpmVersionAvailable(target);
          return isAvailable ? undefined : target;
        }),
      );
      pending = unavailable.filter(target => target !== undefined);
      return pending.length === 0;
    },
    { attempts: DEPENDENCY_POLL_ATTEMPTS, intervalMs: DEPENDENCY_POLL_INTERVAL_MS, until: true },
  );
  ensure(
    pending.length === 0,
    `npm dependencies did not become available: ${pending.map(target => `${target.label}@${target.version}`).join(', ')}`,
  );
};
