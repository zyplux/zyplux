import type { FetchFake, TempDir } from '@zyplux/spectra';

import { readFile } from 'node:fs/promises';
import path from 'node:path';
export type UpgradeWorkspace = {
  readDockerfile: () => Promise<string>;
  stage: (options?: { nodeVersion?: string; python?: boolean; turbo?: boolean }) => Promise<void>;
  stubReleases: () => void;
};
const NODE_INDEX_URL = 'https://nodejs.org/dist/index.json';
const DOCKER_AUTH_URL = 'https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/node:pull';
const DOCKER_MANIFEST_URL = 'https://registry-1.docker.io/v2/library/node/manifests/';
const JSON_INDENT = 2;

export const createUpgradeWorkspace = (network: FetchFake, tempDir: TempDir): UpgradeWorkspace => ({
  readDockerfile: () => readFile(path.join(tempDir.path, 'apps/demo/Dockerfile'), 'utf8'),
  stage: async ({ nodeVersion = '26.7.0', python = false, turbo = true } = {}) => {
    const manifest = {
      devEngines: { runtime: { name: 'node', onFail: 'download', version: nodeVersion } },
      name: 'fixture',
      packageManager: 'pnpm@12.0.0-rc.11',
      private: true,
      ...(turbo && { toolchain: { turbo: '2.10' } }),
    };
    await tempDir.write('package.json', `${JSON.stringify(manifest, undefined, JSON_INDENT)}\n`);
    await tempDir.write('apps/demo/Dockerfile', `ARG NODE_VERSION=${nodeVersion}\nFROM node:\${NODE_VERSION}-slim\n`);
    if (python) await tempDir.write('pyproject.toml', '[project]\nname = "fixture"\nversion = "0.0.0"\n');
  },
  stubReleases: () => {
    network.on(NODE_INDEX_URL, () =>
      Response.json([{ version: 'v27.1.0' }, { version: 'v26.8.0' }, { version: 'v26.7.1' }]),
    );
    network.on(DOCKER_AUTH_URL, () => Response.json({ token: 'registry-token' }));
    network.on(`${DOCKER_MANIFEST_URL}26.8.0-slim`, () => new Response(undefined, { status: 404 }));
    network.on(
      `${DOCKER_MANIFEST_URL}26.7.1-slim`,
      () => new Response(undefined, { headers: { 'docker-content-digest': 'sha256:deployable' } }),
    );
    network.on('https://registry.npmjs.org/turbo/latest', () => Response.json({ version: '2.11.3' }));
  },
});
