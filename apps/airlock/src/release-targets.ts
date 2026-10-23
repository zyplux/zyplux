import { ensure } from '@zyplux/util/assert';
import { FetchError, http } from '@zyplux/util/http';
import { parseJson } from '@zyplux/util/json';
import { $, readTrimmed } from '@zyplux/util/shell';
import { parseToml } from '@zyplux/util/toml';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

import type { ActionTarget, Target, VersionSource } from './contracts.ts';

import { isActionPublished } from './action-releases.ts';
import {
  GhcrTokenSchema,
  ManifestSchema,
  NpmPackageSchema,
  NpmVersionsSchema,
  PypiFilesSchema,
  RegistryUrlSchema,
  VersionFieldSchema,
  VersionFileSchema,
} from './contracts.ts';

export type ReleaseTarget = {
  action: ActionTarget | undefined;
  artifactCommand: [string, ...string[]] | undefined;
  assets: string[];
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

const readVersion = async (repoRoot: string, source: VersionSource) => {
  const text = await readFile(path.join(repoRoot, source.file), 'utf8');
  if ('json' in source) {
    const fields = parseJson(text, VersionFileSchema);
    return VersionFieldSchema.parse(fields[source.json]);
  }
  const version = new RegExp(source.regex, 'm').exec(text)?.[1];
  if (version === undefined) {
    throw new Error(`could not read version from ${source.file}`);
  }
  return version;
};

const MANIFEST_MEDIA_TYPES = [
  'application/vnd.oci.image.index.v1+json',
  'application/vnd.oci.image.manifest.v1+json',
  'application/vnd.docker.distribution.manifest.list.v2+json',
  'application/vnd.docker.distribution.manifest.v2+json',
].join(', ');

const HTTP_NOT_FOUND = 404;

const isRegistryPublished = async (isPublished: () => Promise<boolean>) => {
  try {
    return await isPublished();
  } catch (error) {
    if (error instanceof FetchError && error.response.status === HTTP_NOT_FOUND) return false;
    throw error;
  }
};

const isGhcrImagePublished = (repo: string, tag: string) =>
  isRegistryPublished(async () => {
    const ghToken = process.env['GH_TOKEN'];
    const token = ghToken !== undefined && ghToken.length > 0 ? ghToken : process.env['NODE_AUTH_TOKEN'];
    const actor = process.env['GITHUB_ACTOR'];
    const headers: Record<string, string> = {};
    if (token && actor) headers['Authorization'] = `Basic ${Buffer.from(`${actor}:${token}`).toString('base64')}`;
    const auth = await http
      .get(`https://ghcr.io/token?service=ghcr.io&scope=repository:${repo}:pull`, { headers })
      .json(GhcrTokenSchema);
    await http
      .head(`https://ghcr.io/v2/${repo}/manifests/${tag}`, {
        headers: { Accept: MANIFEST_MEDIA_TYPES, Authorization: `Bearer ${auth.token}` },
      })
      .response();
    return true;
  });

const loadNpmRegistry = async (directory: string, label: string) => {
  const { publishConfig } = parseJson(await readFile(path.join(directory, 'package.json'), 'utf8'), NpmPackageSchema);
  const registryKey = label.startsWith('@') ? `${label.split('/', 1)[0]}:registry` : 'registry';
  return RegistryUrlSchema.parse(
    Object.hasOwn(publishConfig, registryKey) ? publishConfig[registryKey] : publishConfig['registry'],
  );
};

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

const isNpmPublished = async (directory: string, label: string, version: string) => {
  const registry = await loadNpmRegistry(directory, label);
  const headers: Record<string, string> = {};
  if (registry === 'https://npm.pkg.github.com') {
    const token = process.env['NODE_AUTH_TOKEN'];
    ensure(token !== undefined && token.length > 0, 'NODE_AUTH_TOKEN is required to read npm.pkg.github.com');
    headers['Authorization'] = `Bearer ${token}`;
  }
  const packageUrl = `${registry}/${encodeURIComponent(label)}`;
  return isRegistryPublished(async () => {
    const { versions } = await http.get(packageUrl, { headers }).json(NpmVersionsSchema);
    return Object.hasOwn(versions, version);
  });
};

const isPackagePublished = async (target: Target, version: string, directory: string) => {
  if (target.kind === 'action') return isActionPublished(target, version);
  const { kind, label } = target;
  if (kind === 'npm') {
    return isNpmPublished(directory, label, version);
  }
  if (kind === 'pypi') {
    return isRegistryPublished(async () => {
      const { urls } = await http.get(`https://pypi.org/pypi/${label}/${version}/json`).json(PypiFilesSchema);
      return ['bdist_wheel', 'sdist'].every(kind => urls.some(file => file.packagetype === kind));
    });
  }
  return isGhcrImagePublished(label.replace(/^ghcr\.io\//, ''), version);
};

export const loadReleaseTargets = async (): Promise<ReleaseTarget[]> => {
  const repoRoot = await readTrimmed($.git.showToplevel());
  const manifest = parseToml(await readFile(path.join(repoRoot, 'release-targets.toml'), 'utf8'), ManifestSchema);
  return Promise.all(
    manifest.target.map(async spec => {
      const dir = path.join(repoRoot, path.dirname(spec.version.file));
      const version = await readVersion(repoRoot, spec.version);
      return {
        action: spec.kind === 'action' ? spec : undefined,
        artifactCommand: spec.kind === 'ghcr' ? spec.artifact_command : undefined,
        assets: spec.kind === 'ghcr' ? spec.assets : [],
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
  ensure(target !== undefined, `no release target in release-targets.toml owns tag '${tag}'`);

  ensure(
    tag === target.tag,
    `tag '${tag}' does not match ${target.label} version '${target.version}' (expected '${target.tag}')`,
  );
  return target;
};
