import type { FetchFake } from '@zyplux/spectra/fetch-fake';
import type { RepositoryFake } from '@zyplux/spectra/repository-fake';
import type { ShellFake } from '@zyplux/spectra/shell-fake';
import type { TempDir } from '@zyplux/spectra/temp-directory';

import { ManifestSchema } from '@zyplux/airlock/contracts';
import { notFoundResponse, okResponse } from '@zyplux/spectra/fetch-fake';
import { ensure } from '@zyplux/util/assert';
import { parseToml } from '@zyplux/util/toml';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const workspaceRoot = fileURLToPath(new URL('../../../../', import.meta.url));
export type LiveWorkspace = {
  root: string;
  targetLabels: () => Promise<string[]>;
};

export type NpmTarget = {
  setPublishConfig: (publishConfig: Record<string, unknown>) => Promise<void>;
  stagePublish: (exitCode?: number) => void;
};

export type Registries = {
  denyGhcrAuth: () => void;
  setPublished: (published: RegistryPublishedState) => void;
};

export type Release = {
  stageAllPublished: () => void;
  stagePendingCerberus: () => void;
};

export type SeededTargets = {
  cerberus: TargetFacts;
  ci: TargetFacts;
  configureTarget: (kind: string, fields: string) => Promise<void>;
  util: TargetFacts;
};
type RegistryPublishedState = {
  ghcrPublished?: boolean;
  npmPublished?: boolean;
  pypiPublished?: boolean;
};

type TargetFacts = { dir: string; label: string; tag: string; version: string };

export const createNpmTarget = (shell: ShellFake, tempDir: TempDir) =>
  ({
    setPublishConfig: async publishConfig => {
      await tempDir.write(
        'packages/util/package.json',
        JSON.stringify({ name: '@zyplux/util', publishConfig, version: '1.2.3' }),
      );
    },
    stagePublish: (exitCode = 0) => {
      shell.on('pnpm pack', '');
      shell.on('pnpm publish', { exitCode, stdout: '' });
    },
  }) satisfies NpmTarget;

export const createRegistries = (network: FetchFake) =>
  ({
    denyGhcrAuth: () => {
      network.on('https://ghcr.io/token', () => notFoundResponse());
    },
    setPublished: ({ ghcrPublished = false, npmPublished = false, pypiPublished = false }) => {
      network.on('https://ghcr.io/token', () => Response.json({ token: 'gh-token' }));
      network.on('https://ghcr.io/v2/', () => (ghcrPublished ? okResponse() : notFoundResponse()));
      network.on('https://pypi.org/', () =>
        pypiPublished
          ? Response.json({ urls: [{ packagetype: 'bdist_wheel' }, { packagetype: 'sdist' }] })
          : notFoundResponse(),
      );
      network.on('https://registry.npmjs.org/', () =>
        npmPublished ? Response.json({ versions: { '1.2.3': {} } }) : notFoundResponse(),
      );
    },
  }) satisfies Registries;
export const createRelease = (repo: RepositoryFake, registries: Registries, shell: ShellFake) =>
  ({
    stageAllPublished: () => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: true });
      shell.on('gh api graphql', '{"data":{"repository":{"release":{"id":"release-id"}}}}');
    },
    stagePendingCerberus: () => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: false });
      shell.on('gh api graphql', '{"data":{"repository":{"release":{"id":"release-id"}}}}');
    },
  }) satisfies Release;

const SEEDED_MANIFEST = String.raw`scope = "@zyplux"

[util]
kind = "npm"
surface = []
version = { file = "packages/util/package.json", json = "version" }

[cerberus]
kind = "pypi"
label = "zyplux-cerberus"
surface = []
version = { file = "apps/cerberus/pyproject.toml", regex = '^version = "([^"]+)"' }

[ci-image]
kind = "ghcr"
label = "ghcr.io/zyplux/ci"
surface = []
version = { file = "containers/ci/Containerfile", regex = '^LABEL org\.opencontainers\.image\.version="([^"]+)"' }
`;

export const seedReleaseTargets = async (tempDir: TempDir) => {
  await tempDir.write('airlock-targets.toml', SEEDED_MANIFEST);
  await tempDir.write('packages/util/package.json', '{ "name": "@zyplux/util", "version": "1.2.3" }\n');
  await tempDir.write('apps/cerberus/pyproject.toml', '[project]\nname = "zyplux-cerberus"\nversion = "2.3.4"\n');
  await tempDir.write(
    'apps/cerberus/package.json',
    JSON.stringify({ name: 'zyplux-cerberus', private: true, version: '2.3.4' }),
  );
  await tempDir.write('containers/ci/Containerfile', 'FROM scratch\nLABEL org.opencontainers.image.version="3.4.5"\n');
  await tempDir.write('.changeset/README.md', '# Release notes\n');
  for (const [directory, version, notes] of [
    ['packages/util', '1.2.3', 'Publish the reviewed utility changes.'],
    ['apps/cerberus', '2.3.4', 'Validate repository release contracts.'],
    ['containers/ci', '3.4.5', 'Refresh the CI container.'],
  ]) {
    await tempDir.write(
      `${directory}/CHANGELOG.md`,
      `# Releases\n\n## ${version}\n\n### Patch Changes\n\n- ${notes}\n`,
    );
  }

  return {
    cerberus: {
      dir: path.join(tempDir.path, 'apps/cerberus'),
      label: 'zyplux-cerberus',
      tag: 'cerberus-v2.3.4',
      version: '2.3.4',
    },
    ci: {
      dir: path.join(tempDir.path, 'containers/ci'),
      label: 'ghcr.io/zyplux/ci',
      tag: 'ci-image-v3.4.5',
      version: '3.4.5',
    },
    configureTarget: async (kind, fields) => {
      const manifest = await readFile(path.join(tempDir.path, 'airlock-targets.toml'), 'utf8');
      const sections = manifest.split(/(?=^\[)/mu);
      const index = sections.findIndex(section => section.includes(`kind = "${kind}"`));
      const section = sections[index];
      ensure(section !== undefined, 'target kind must exist');
      const lines = section.split('\n');
      for (const field of fields.split('\n')) {
        const key = field.split('=', 1)[0]?.trim();
        const position = lines.findIndex(line => line.startsWith(`${key} =`));
        if (position === -1) lines.push(field);
        else lines[position] = field;
      }
      sections[index] = `${lines.join('\n')}\n`;
      await tempDir.write('airlock-targets.toml', sections.join(''));
    },
    util: {
      dir: path.join(tempDir.path, 'packages/util'),
      label: '@zyplux/util',
      tag: 'util-v1.2.3',
      version: '1.2.3',
    },
  } satisfies SeededTargets;
};

export const createLiveWorkspace = () =>
  ({
    root: workspaceRoot,
    targetLabels: async () => {
      const manifestText = await readFile(path.join(workspaceRoot, 'airlock-targets.toml'), 'utf8');
      return parseToml(manifestText, ManifestSchema).target.map(target => target.label);
    },
  }) satisfies LiveWorkspace;
