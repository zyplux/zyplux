import type { FetchFake } from '@zyplux/spectra/fetch-fake';
import type { RepositoryFake } from '@zyplux/spectra/repository-fake';
import type { ShellFake } from '@zyplux/spectra/shell-fake';
import type { TempDir } from '@zyplux/spectra/temp-directory';

import { ManifestSchema } from '@zyplux/airlock/contracts';
import { notFoundResponse, okResponse } from '@zyplux/spectra/fetch-fake';
import { parseToml } from '@zyplux/util/toml';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import { vi } from 'vitest';
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
  completeRunAfter: (runId: string, predecessorId: string, conclusion: string) => void;
  queueRun: (runId: string, first: RunState, ...later: RunState[]) => void;
  stageAllPublished: () => void;
  stagePendingCerberus: (options?: PendingCerberusOptions) => void;
  stagePendingCerberusAndCiImage: () => void;
};

export type SeededTargets = {
  cerberus: TargetFacts;
  ci: TargetFacts;
  util: TargetFacts;
};
type PendingCerberusOptions = {
  published?: RegistryPublishedState;
  tagRunPolls?: [string[], ...string[][]];
};
type RegistryPublishedState = {
  ghcrEverVisible?: boolean;
  ghcrPublished?: boolean;
  npmPublished?: boolean;
  pypiEverVisible?: boolean;
  pypiPublished?: boolean;
};

type RunState = { conclusion?: string; status: string };

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
    setPublished: ({
      ghcrEverVisible,
      ghcrPublished = false,
      npmPublished = false,
      pypiEverVisible,
      pypiPublished = false,
    }) => {
      let ghcrProbeCount = 0;
      let pypiProbeCount = 0;
      network.on('https://ghcr.io/token', () => Response.json({ token: 'gh-token' }));
      network.on('https://ghcr.io/v2/', () => {
        ghcrProbeCount += 1;
        if (ghcrProbeCount === 1) return ghcrPublished ? okResponse() : notFoundResponse();
        return ghcrEverVisible === false ? notFoundResponse() : okResponse();
      });
      network.on('https://pypi.org/', () => {
        pypiProbeCount += 1;
        const isPublished = pypiProbeCount === 1 ? pypiPublished : pypiEverVisible !== false;
        return isPublished
          ? Response.json({ urls: [{ packagetype: 'bdist_wheel' }, { packagetype: 'sdist' }] })
          : notFoundResponse();
      });
      network.on('https://registry.npmjs.org/', () =>
        npmPublished ? Response.json({ versions: { '1.2.3': {} } }) : notFoundResponse(),
      );
    },
  }) satisfies Registries;
const renderRunIds = (ids: string[]) => JSON.stringify(ids.map(id => ({ databaseId: Number(id) })));

const renderRun = ({ conclusion = '', status }: RunState) => JSON.stringify({ conclusion, status });

export const createRelease = (repo: RepositoryFake, registries: Registries, shell: ShellFake) => {
  const queueRun = (runId: string, first: RunState, ...later: RunState[]) => {
    shell.on(`gh run view ${runId}`, renderRun(first), ...later.map(run => renderRun(run)));
  };

  return {
    completeRunAfter: (runId, predecessorId, conclusion) => {
      let isPredecessorCompleted = false;
      const predecessorCompletion = Promise.withResolvers<undefined>();
      vi.mocked(sleep).mockImplementation(() => predecessorCompletion.promise);
      shell.on(`gh run view ${predecessorId}`, () => {
        isPredecessorCompleted = true;
        predecessorCompletion.resolve(undefined);
        return renderRun({ conclusion, status: 'completed' });
      });
      shell.on(`gh run view ${runId}`, () =>
        renderRun({
          conclusion,
          status: isPredecessorCompleted ? 'completed' : 'in_progress',
        }),
      );
    },
    queueRun,
    stageAllPublished: () => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: true });
    },
    stagePendingCerberus: ({ published, tagRunPolls = [['100', '101', '999']] }: PendingCerberusOptions = {}) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: false, ...published });
      shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');
      shell.on('gh run list', renderRunIds(['100', '101']), ...tagRunPolls.map(ids => renderRunIds(ids)));
    },
    stagePendingCerberusAndCiImage: () => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: false, npmPublished: true, pypiPublished: false });
      shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');
      shell.on(/^gh run list --branch cerberus-v/, renderRunIds(['100']), renderRunIds(['100', '111']));
      shell.on(/^gh run list --branch ci-image-v/, renderRunIds(['100']), renderRunIds(['100', '222']));
    },
  } satisfies Release;
};

const SEEDED_MANIFEST = String.raw`[[target]]
kind = "npm"
label = "@zyplux/util"
surface = []
tag_prefix = "util-v"
version = { file = "packages/util/package.json", json = "version" }

[[target]]
kind = "pypi"
label = "zyplux-cerberus"
surface = []
tag_prefix = "cerberus-v"
version = { file = "apps/cerberus/pyproject.toml", regex = '^version = "([^"]+)"' }

[[target]]
kind = "ghcr"
label = "ghcr.io/zyplux/ci"
surface = []
tag_prefix = "ci-image-v"
version = { file = "containers/ci/Containerfile", regex = '^LABEL org\.opencontainers\.image\.version="([^"]+)"' }
`;

export const seedReleaseTargets = async (tempDir: TempDir) => {
  await tempDir.write('release-targets.toml', SEEDED_MANIFEST);
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
      const manifestText = await readFile(path.join(workspaceRoot, 'release-targets.toml'), 'utf8');
      return parseToml(manifestText, ManifestSchema).target.map(target => target.label);
    },
  }) satisfies LiveWorkspace;
