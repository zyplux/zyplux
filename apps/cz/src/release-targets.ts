import { $, ensure, fetchJson, httpOk, parseJson, parseToml, readTrimmed } from '@zyplux/util';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

import type { Target, VersionSource } from '#contracts';

import { GhcrTokenSchema, ManifestSchema, VersionFieldSchema, VersionFileSchema } from '#contracts';

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

const fetchGhcrAuth = (repo: string) =>
  fetchJson(`https://ghcr.io/token?scope=repository:${repo}:pull`, GhcrTokenSchema);

const ghcrImagePublished = async (repo: string, tag: string) => {
  const auth = await fetchGhcrAuth(repo);
  if (!auth) return false;
  return httpOk(`https://ghcr.io/v2/${repo}/manifests/${tag}`, {
    headers: {
      Accept: MANIFEST_MEDIA_TYPES,
      Authorization: `Bearer ${auth.token}`,
    },
    method: 'HEAD',
  });
};

const checkPackagePublished = async ({ kind, label }: Target, version: string) => {
  if (kind === 'npm') {
    return httpOk(`https://registry.npmjs.org/${label.replace('/', '%2f')}/${version}`);
  }
  if (kind === 'pypi') {
    return httpOk(`https://pypi.org/pypi/${label}/${version}/json`);
  }
  return ghcrImagePublished(label.replace(/^ghcr\.io\//, ''), version);
};

export const loadReleaseTargets = async (): Promise<ReleaseTarget[]> => {
  const repoRoot = await readTrimmed($.git.showToplevel());
  const manifest = parseToml(await readFile(path.join(repoRoot, 'release-targets.toml'), 'utf8'), ManifestSchema);
  return manifest.target.map(spec => ({
    dir: path.join(repoRoot, path.dirname(spec.version.file)),
    isPublished: async (version: string) => checkPackagePublished(spec, version),
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
