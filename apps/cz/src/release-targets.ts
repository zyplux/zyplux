import { readFile } from 'node:fs/promises';

export type ReleaseTarget = {
  isPublished: (version: string) => Promise<boolean>;
  label: string;
  readSurface: () => string[];
  readVersion: () => Promise<string>;
  tagPrefix: string;
};

const httpOk = async (url: string) => {
  const response = await fetch(url);
  return response.ok;
};

const MANIFEST_MEDIA_TYPES = [
  'application/vnd.oci.image.index.v1+json',
  'application/vnd.oci.image.manifest.v1+json',
  'application/vnd.docker.distribution.manifest.list.v2+json',
  'application/vnd.docker.distribution.manifest.v2+json',
].join(', ');

const ghcrImagePublished = async (repo: string, tag: string) => {
  const tokenResponse = await fetch(`https://ghcr.io/token?scope=repository:${repo}:pull`);
  if (!tokenResponse.ok) return false;
  const body: unknown = await tokenResponse.json();
  if (typeof body !== 'object' || body === null || !('token' in body)) return false;
  const { token } = body;
  if (typeof token !== 'string') return false;
  const manifest = await fetch(`https://ghcr.io/v2/${repo}/manifests/${tag}`, {
    headers: {
      Accept: MANIFEST_MEDIA_TYPES,
      Authorization: `Bearer ${token}`,
    },
    method: 'HEAD',
  });
  return manifest.ok;
};

const fromRoot = (path: string) => new URL(`../../../${path}`, import.meta.url);

const readJsonVersion = async (dir: string) => {
  const parsed: unknown = JSON.parse(await readFile(fromRoot(`${dir}/package.json`), 'utf8'));
  if (typeof parsed === 'object' && parsed !== null && 'version' in parsed && typeof parsed.version === 'string') {
    return parsed.version;
  }
  throw new Error(`could not read version from ${dir}/package.json`);
};

const matchVersion = async (url: URL, pattern: RegExp, label: string) => {
  const text = await readFile(url, 'utf8');
  const version = pattern.exec(text)?.[1];
  if (version === undefined) {
    throw new Error(`could not read ${label}`);
  }
  return version;
};

export const releaseTargets: ReleaseTarget[] = [
  {
    isPublished: async version => httpOk(`https://registry.npmjs.org/@zyplux%2feslint-config/${version}`),
    label: '@zyplux/eslint-config',
    readSurface: () => [
      'packages/eslint-config/package.json',
      'packages/eslint-config/README.md',
      'packages/eslint-config/src',
    ],
    readVersion: async () => readJsonVersion('packages/eslint-config'),
    tagPrefix: 'eslint-config-v',
  },
  {
    isPublished: async version => httpOk(`https://registry.npmjs.org/@zyplux%2ftsconfig/${version}`),
    label: '@zyplux/tsconfig',
    readSurface: () => ['packages/tsconfig'],
    readVersion: async () => readJsonVersion('packages/tsconfig'),
    tagPrefix: 'tsconfig-v',
  },
  {
    isPublished: async version => httpOk(`https://pypi.org/pypi/zyplux-cerberus/${version}/json`),
    label: 'zyplux-cerberus',
    readSurface: () => ['apps/cerberus/src', 'apps/cerberus/pyproject.toml', 'apps/cerberus/README.md'],
    readVersion: async () =>
      matchVersion(fromRoot('apps/cerberus/pyproject.toml'), /^version = "([^"]+)"/m, 'cerberus version'),
    tagPrefix: 'cerberus-v',
  },
  {
    isPublished: async version => ghcrImagePublished('zyplux/ci', version),
    label: 'ghcr.io/zyplux/ci',
    readSurface: () => ['containers/ci'],
    readVersion: async () =>
      matchVersion(
        fromRoot('containers/ci/Containerfile'),
        /^LABEL org\.opencontainers\.image\.version="([^"]+)"/m,
        'image version',
      ),
    tagPrefix: 'ci-image-v',
  },
];
