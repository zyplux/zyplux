import { ensure } from '@zyplux/util/assert';
import { FetchError, http } from '@zyplux/util/http';
import { parseJson } from '@zyplux/util/json';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { rcompare, valid } from 'semver';

import type { Target } from './contracts.ts';

import { fetchActionReleases, isActionPublished } from './action-releases.ts';
import {
  GhcrTagsSchema,
  GhcrTokenSchema,
  NpmLatestSchema,
  NpmPackageSchema,
  NpmVersionsSchema,
  PypiFilesSchema,
  PypiLatestSchema,
  RegistryUrlSchema,
} from './contracts.ts';

const MANIFEST_MEDIA_TYPES = [
  'application/vnd.oci.image.index.v1+json',
  'application/vnd.oci.image.manifest.v1+json',
  'application/vnd.docker.distribution.manifest.list.v2+json',
  'application/vnd.docker.distribution.manifest.v2+json',
].join(', ');

const HTTP_NOT_FOUND = 404;

const findRegistryEntry = async <Entry>(fetchEntry: () => Promise<Entry>) => {
  try {
    return await fetchEntry();
  } catch (error) {
    if (error instanceof FetchError && error.response.status === HTTP_NOT_FOUND) return;
    throw error;
  }
};

const fetchGhcrToken = async (image: string) => {
  const ghToken = process.env['GH_TOKEN'];
  const token = ghToken !== undefined && ghToken.length > 0 ? ghToken : process.env['NODE_AUTH_TOKEN'];
  const actor = process.env['GITHUB_ACTOR'];
  const headers: Record<string, string> = {};
  if (token && actor) headers['Authorization'] = `Basic ${Buffer.from(`${actor}:${token}`).toString('base64')}`;
  return http
    .get(`https://ghcr.io/token?service=ghcr.io&scope=repository:${image}:pull`, { headers })
    .json(GhcrTokenSchema);
};

export const loadNpmRegistry = async (directory: string, label: string) => {
  const { publishConfig } = parseJson(await readFile(path.join(directory, 'package.json'), 'utf8'), NpmPackageSchema);
  const registryKey = label.startsWith('@') ? `${label.split('/', 1)[0]}:registry` : 'registry';
  return RegistryUrlSchema.parse(
    Object.hasOwn(publishConfig, registryKey) ? publishConfig[registryKey] : publishConfig['registry'],
  );
};

const loadNpmRequest = async (directory: string, label: string) => {
  const registry = await loadNpmRegistry(directory, label);
  const headers: Record<string, string> = {};
  if (registry === 'https://npm.pkg.github.com') {
    const token = process.env['NODE_AUTH_TOKEN'];
    ensure(token !== undefined && token.length > 0, 'NODE_AUTH_TOKEN is required to read npm.pkg.github.com');
    headers['Authorization'] = `Bearer ${token}`;
  }
  return http.get(`${registry}/${encodeURIComponent(label)}`, { headers });
};

export const isPackagePublished = async (target: Target, version: string, directory: string) => {
  if (target.kind === 'action') return isActionPublished(target, version);
  return (
    (await findRegistryEntry(async () => {
      const { kind, label } = target;
      if (kind === 'npm') {
        const request = await loadNpmRequest(directory, label);
        const { versions } = await request.json(NpmVersionsSchema);
        return Object.hasOwn(versions, version);
      }
      if (kind === 'pypi') {
        const { urls } = await http.get(`https://pypi.org/pypi/${label}/${version}/json`).json(PypiFilesSchema);
        return ['bdist_wheel', 'sdist'].every(kind => urls.some(file => file.packagetype === kind));
      }
      const image = label.replace(/^ghcr\.io\//u, '');
      const { token } = await fetchGhcrToken(image);
      await http
        .head(`https://ghcr.io/v2/${image}/manifests/${version}`, {
          headers: { Accept: MANIFEST_MEDIA_TYPES, Authorization: `Bearer ${token}` },
        })
        .response();
      return true;
    })) ?? false
  );
};

export const fetchLatestVersion = async (target: Target, directory: string) =>
  findRegistryEntry(async () => {
    if (target.kind === 'action') {
      const releases = await fetchActionReleases(target);
      return releases[0]?.version.version;
    }
    const { kind, label } = target;
    if (kind === 'npm') {
      const request = await loadNpmRequest(directory, label);
      const metadata = await request.json(NpmLatestSchema);
      return metadata['dist-tags'].latest;
    }
    if (kind === 'pypi') {
      const { info } = await http.get(`https://pypi.org/pypi/${label}/json`).json(PypiLatestSchema);
      return info.version;
    }
    const image = label.replace(/^ghcr\.io\//u, '');
    const { token } = await fetchGhcrToken(image);
    const { tags } = await http
      .get(`https://ghcr.io/v2/${image}/tags/list`, { headers: { Authorization: `Bearer ${token}` } })
      .json(GhcrTagsSchema);
    return (tags ?? []).filter(tag => valid(tag) === tag && !tag.includes('-')).toSorted(rcompare)[0];
  });
