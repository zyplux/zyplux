import { ensure } from '@zyplux/util/assert';
import { parseJson } from '@zyplux/util/json';
import { $, readTrimmed } from '@zyplux/util/shell';
import { parseToml } from '@zyplux/util/toml';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

import type { ActionTarget, Target, VersionSource } from './contracts.ts';

import { ManifestSchema, VersionFieldSchema, VersionFileSchema } from './contracts.ts';
import { isPackagePublished, loadNpmRegistry } from './release-registries.ts';

export type ReleaseTarget = {
  action: ActionTarget | undefined;
  container: undefined | { buildContext: string; dockerfile: string | undefined };
  dir: string;
  environment: string;
  isPublished: () => Promise<boolean>;
  kind: Target['kind'];
  label: string;
  tag: string;
  tagPrefix: string;
  version: string;
  versionFile: string;
};

export const parseTargetVersion = (text: string, source: VersionSource) => {
  if ('json' in source) {
    let field: unknown = parseJson(text, VersionFileSchema);
    for (const key of source.json.split('.')) field = VersionFileSchema.parse(field)[key];
    return VersionFieldSchema.parse(field);
  }
  const version = new RegExp(source.regex, 'm').exec(text)?.[1];
  if (version === undefined) {
    throw new Error(`could not read version from ${source.file}`);
  }
  return version;
};

export const loadReleaseSpecs = async (root: string) =>
  parseToml(await readFile(path.join(root, 'airlock-targets.toml'), 'utf8'), ManifestSchema).target;

export const loadRegistryArgs = async (targets: ReleaseTarget[]) => {
  const registries = new Map<string, string>();
  for (const target of targets) {
    if (target.kind !== 'npm') continue;
    const key = target.label.startsWith('@') ? `${target.label.split('/', 1)[0]}:registry` : 'registry';
    const registry = await loadNpmRegistry(target.dir, target.label);
    ensure(
      !registries.has(key) || registries.get(key) === registry,
      `native pnpm preparation requires one publication registry per scope (${key})`,
    );
    registries.set(key, registry);
  }
  return Array.from(registries, ([key, registry]) => `--config.${key}=${registry}`);
};

const resolveBuildPath = (root: string, relative: string) => {
  const resolved = path.resolve(root, relative);
  ensure(
    !path.isAbsolute(relative) && (resolved === root || resolved.startsWith(`${root}${path.sep}`)),
    `container build paths must be repository-relative: ${relative}`,
  );
  return resolved;
};

export const loadReleaseTargets = async (): Promise<ReleaseTarget[]> => {
  const repoRoot = await readTrimmed($.git.showToplevel());
  const targets = await loadReleaseSpecs(repoRoot);
  return Promise.all(
    targets.map(async spec => {
      const dir = path.join(repoRoot, path.dirname(spec.version.file));
      const version = parseTargetVersion(await readFile(path.join(repoRoot, spec.version.file), 'utf8'), spec.version);
      return {
        action: spec.kind === 'action' ? spec : undefined,
        container:
          spec.kind === 'ghcr'
            ? {
                buildContext: resolveBuildPath(repoRoot, spec.build_context ?? path.dirname(spec.version.file)),
                dockerfile: spec.dockerfile === undefined ? undefined : resolveBuildPath(repoRoot, spec.dockerfile),
              }
            : undefined,
        dir,
        environment: spec.environment ?? (spec.kind === 'action' ? 'actions' : spec.kind),
        isPublished: async () => isPackagePublished(spec, version, dir),
        kind: spec.kind,
        label: spec.label,
        tag: `${spec.tag_prefix}${version}`,
        tagPrefix: spec.tag_prefix,
        version,
        versionFile: spec.version.file,
      };
    }),
  );
};

export const resolveReleaseTag = async (tag: string): Promise<ReleaseTarget> => {
  const targets = await loadReleaseTargets();
  const target = targets.find(candidate => tag.startsWith(candidate.tagPrefix));
  ensure(target !== undefined, `no release target in airlock-targets.toml owns tag '${tag}'`);

  ensure(
    tag === target.tag,
    `tag '${tag}' does not match ${target.label} version '${target.version}' (expected '${target.tag}')`,
  );
  return target;
};
