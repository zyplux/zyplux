import { ensure } from '@zyplux/util/assert';
import { FetchError, fetchJson, http, isHttpOk } from '@zyplux/util/http';
import { parseJson } from '@zyplux/util/json';
import { $, readTrimmed } from '@zyplux/util/shell';
import { parseToml } from '@zyplux/util/toml';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

import type { Target, VersionSource } from './contracts.ts';

import {
  GhcrTokenSchema,
  ManifestSchema,
  NpmPackageSchema,
  VersionFieldSchema,
  VersionFileSchema,
} from './contracts.ts';

export type ReleaseTarget = {
  dir: string;
  isPublished: (version: string) => Promise<boolean>;
  kind: Target['kind'];
  label: string;
  readVersion: () => Promise<string>;
  tagPrefix: string;
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

const fetchGhcrAuth = (repo: string) =>
  fetchJson(`https://ghcr.io/token?scope=repository:${repo}:pull`, GhcrTokenSchema);

const isGhcrImagePublished = async (repo: string, tag: string) => {
  const auth = await fetchGhcrAuth(repo);
  if (!auth) return false;
  return isHttpOk(`https://ghcr.io/v2/${repo}/manifests/${tag}`, {
    headers: {
      Accept: MANIFEST_MEDIA_TYPES,
      Authorization: `Bearer ${auth.token}`,
    },
    method: 'HEAD',
  });
};

const isNpmPublished = async (directory: string, label: string, version: string) => {
  const { publishConfig } = parseJson(await readFile(path.join(directory, 'package.json'), 'utf8'), NpmPackageSchema);
  const headers: Record<string, string> = {};
  if (publishConfig.registry === 'https://npm.pkg.github.com') {
    const token = process.env['NODE_AUTH_TOKEN'];
    ensure(token !== undefined && token.length > 0, 'NODE_AUTH_TOKEN is required to read npm.pkg.github.com');
    headers['Authorization'] = `Bearer ${token}`;
  }
  try {
    await http.get(`${publishConfig.registry}/${encodeURIComponent(label)}/${version}`, { headers }).response();
    return true;
  } catch (error) {
    if (error instanceof FetchError && error.response.status === HTTP_NOT_FOUND) return false;
    throw error;
  }
};

const isPackagePublished = async ({ kind, label }: Target, version: string, directory: string) => {
  if (kind === 'npm') {
    return isNpmPublished(directory, label, version);
  }
  return kind === 'pypi'
    ? isHttpOk(`https://pypi.org/pypi/${label}/${version}/json`)
    : isGhcrImagePublished(label.replace(/^ghcr\.io\//, ''), version);
};

export const loadReleaseTargets = async (): Promise<ReleaseTarget[]> => {
  const repoRoot = await readTrimmed($.git.showToplevel());
  const manifest = parseToml(await readFile(path.join(repoRoot, 'release-targets.toml'), 'utf8'), ManifestSchema);
  return manifest.target.map(spec => ({
    dir: path.join(repoRoot, path.dirname(spec.version.file)),
    isPublished: async (version: string) =>
      isPackagePublished(spec, version, path.join(repoRoot, path.dirname(spec.version.file))),
    kind: spec.kind,
    label: spec.label,
    readVersion: async () => readVersion(repoRoot, spec.version),
    tagPrefix: spec.tag_prefix,
  }));
};

export const resolveReleaseTag = async (tag: string): Promise<{ target: ReleaseTarget; version: string }> => {
  const targets = await loadReleaseTargets();
  const target = targets.find(candidate => tag.startsWith(candidate.tagPrefix));
  ensure(target !== undefined, `no release target in release-targets.toml owns tag '${tag}'`);

  const version = await target.readVersion();
  const expected = `${target.tagPrefix}${version}`;
  ensure(tag === expected, `tag '${tag}' does not match ${target.label} version '${version}' (expected '${expected}')`);

  return { target, version };
};
