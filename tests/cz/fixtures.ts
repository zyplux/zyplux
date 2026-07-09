import type { CliRunner, ConsoleCapture, FetchFake, ShellFake, TempDir } from '@zyplux/tests-fixtures';

import { runCz } from '@zyplux/cz';
import { DepsCatalogSchema, ManifestSchema } from '@zyplux/cz/contracts';
import { cliTest, createCliRunner, notFoundResponse, okResponse } from '@zyplux/tests-fixtures';
import { parseJson, parseToml } from '@zyplux/util';
import { execFileSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const workspaceRoot = fileURLToPath(new URL('../../', import.meta.url));

type Catalog = {
  loadRepos: () => Promise<string[]>;
  outPath: string;
  readOutput: (relativePath?: string) => Promise<string>;
  run: (options?: RunCatalogOptions) => Promise<void>;
  runOverWorkspace: () => Promise<void>;
  unresolvedNames: (system: 'npm' | 'pypi') => string[];
  writeManifest: (relativePath: string, content: string) => Promise<void>;
};

type CzFixtures = {
  catalog: Catalog;
  cz: CliRunner;
  liveWorkspace: LiveWorkspace;
  registries: Registries;
  release: Release;
  repo: Repo;
};

type LiveWorkspace = {
  root: string;
  targetLabels: () => Promise<string[]>;
};

type PendingCerberusOptions = {
  published?: RegistryPublishedState;
  tagRunPolls?: [string, ...string[]];
};

type Registries = {
  denyGhcrAuth: () => void;
  setPublished: (published: RegistryPublishedState) => void;
};

type RegistryPublishedState = {
  ghcrEverVisible?: boolean;
  ghcrPublished?: boolean;
  npmPublished?: boolean;
  pypiEverVisible?: boolean;
  pypiPublished?: boolean;
};

type Release = {
  stageAllPublished: () => void;
  stagePendingCerberus: (options?: PendingCerberusOptions) => void;
  stagePendingCerberusAndCiImage: () => void;
};

type Repo = {
  queuePrFields: (fields: Record<string, [string, ...string[]] | string>) => void;
  setCopilotReviewedHead: (sha: string) => void;
  setCurrentBranch: (branch: string) => void;
  setHeadSha: (sha: string) => void;
  setPrListState: (state: string) => void;
  setRemoteBranchSha: (branch: string, ...shas: [string, ...string[]]) => void;
  setRemoteMainSha: (sha: string) => void;
  setRepoSlug: (slug: string) => void;
  setRoot: (dir: string) => void;
  setWorkingTreeStatus: (status: string) => void;
  syncFeatureBranch: (branch: string, sha: string) => void;
  syncMain: (sha: string) => void;
};

type RunCatalogOptions = { out?: string };

type SeededTargets = {
  cerberus: TargetFacts;
  ci: TargetFacts;
  util: TargetFacts;
};

type TargetFacts = { dir: string; label: string; tag: string; version: string };

type TargetsFixtures = { targets: SeededTargets };

const BENIGN_WRITE_COMMANDS = [
  'gh pr create',
  'gh pr merge',
  'gh pr ready',
  'gh release create',
  'gh release delete',
  'git branch',
  'git checkout',
  'git fetch',
  'git pull',
  'git push',
];

const createCatalog = (cz: CliRunner, tempDir: TempDir, { logLines }: ConsoleCapture) => {
  const outPath = path.join(tempDir.path, 'catalog.json');
  const readOutput = (relativePath = 'catalog.json') => readFile(path.join(tempDir.path, relativePath), 'utf8');
  const runGit = (...args: string[]) => {
    execFileSync('git', args, { cwd: tempDir.path, stdio: 'ignore' });
  };
  runGit('init', '--quiet');

  return {
    loadRepos: async () => parseJson(await readOutput(), DepsCatalogSchema),
    outPath,
    readOutput,
    run: async ({ out = 'catalog.json' }: RunCatalogOptions = {}) => {
      await cz.run('deps-catalog', '--dir', tempDir.path, '--out', out);
    },
    runOverWorkspace: async () => {
      await cz.run('deps-catalog', '--dir', workspaceRoot, '--out', outPath);
    },
    unresolvedNames: system => {
      const prefix = `  ${system}\t`;
      return logLines.filter(line => line.startsWith(prefix)).map(line => line.slice(prefix.length));
    },
    writeManifest: async (relativePath, content) => {
      await tempDir.write(relativePath, content);
      runGit('add', relativePath);
    },
  } satisfies Catalog;
};

const createLiveWorkspace = () =>
  ({
    root: workspaceRoot,
    targetLabels: async () => {
      const manifestText = await readFile(path.join(workspaceRoot, 'release-targets.toml'), 'utf8');
      return parseToml(manifestText, ManifestSchema).target.map(target => target.label);
    },
  }) satisfies LiveWorkspace;

const createRepo = (shell: ShellFake, { path }: TempDir) => {
  const setRoot = (dir: string) => {
    shell.on('git rev-parse --show-toplevel', dir);
  };
  setRoot(path);
  for (const command of BENIGN_WRITE_COMMANDS) shell.on(command, '');

  const setCurrentBranch = (branch: string) => {
    shell.on('git rev-parse --abbrev-ref HEAD', branch);
  };
  const setHeadSha = (sha: string) => {
    shell.on('git rev-parse HEAD', sha);
  };
  const setRemoteMainSha = (sha: string) => {
    shell.on('git rev-parse origin/main', sha);
  };
  const setWorkingTreeStatus = (status: string) => {
    shell.on('git status --porcelain', status);
  };
  const setRemoteBranchSha = (branch: string, ...shas: [string, ...string[]]) => {
    const [firstSha, ...laterShas] = shas;
    const toRefLine = (sha: string) => `${sha}\trefs/heads/${branch}`;
    shell.on(`git ls-remote origin refs/heads/${branch}`, toRefLine(firstSha), ...laterShas.map(sha => toRefLine(sha)));
  };

  return {
    queuePrFields: fields => {
      for (const [field, values] of Object.entries(fields)) {
        const queued: [string, ...string[]] = typeof values === 'string' ? [values] : values;
        shell.on(`gh pr view --jq .${field}`, ...queued);
      }
    },
    setCopilotReviewedHead: sha => {
      shell.on('gh api', sha);
    },
    setCurrentBranch,
    setHeadSha,
    setPrListState: state => {
      shell.on('gh pr list', state);
    },
    setRemoteBranchSha,
    setRemoteMainSha,
    setRepoSlug: slug => {
      shell.on('gh repo view --jq .nameWithOwner', slug);
    },
    setRoot,
    setWorkingTreeStatus,
    syncFeatureBranch: (branch, sha) => {
      setCurrentBranch(branch);
      setHeadSha(sha);
      setRemoteBranchSha(branch, sha);
    },
    syncMain: sha => {
      setCurrentBranch('main');
      setHeadSha(sha);
      setRemoteMainSha(sha);
      setWorkingTreeStatus('');
    },
  } satisfies Repo;
};

const KNOWN_RUNS_PATTERN = /--json databaseId --workflow/;
const TAG_RUNS_PATTERN = /--json databaseId,headBranch/;

const createRelease = (repo: Repo, registries: Registries, shell: ShellFake) =>
  ({
    stageAllPublished: () => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: true });
    },
    stagePendingCerberus: ({ published, tagRunPolls = ['100\n101\n999'] }: PendingCerberusOptions = {}) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: false, ...published });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100\n101');
      shell.on(TAG_RUNS_PATTERN, ...tagRunPolls);
    },
    stagePendingCerberusAndCiImage: () => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: false, npmPublished: true, pypiPublished: false });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100');
      shell.on(/gh run list.*cerberus-v/, '100\n111');
      shell.on(/gh run list.*ci-image-v/, '100\n222');
    },
  }) satisfies Release;

const createRegistries = (network: FetchFake) =>
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
        if (pypiProbeCount === 1) return pypiPublished ? okResponse() : notFoundResponse();
        return pypiEverVisible === false ? notFoundResponse() : okResponse();
      });
      network.on('https://registry.npmjs.org/', () => (npmPublished ? okResponse() : notFoundResponse()));
      network.otherwise(() => notFoundResponse());
    },
  }) satisfies Registries;

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

const seedReleaseTargets = async (tempDir: TempDir) => {
  await tempDir.write('release-targets.toml', SEEDED_MANIFEST);
  await tempDir.write('packages/util/package.json', '{ "name": "@zyplux/util", "version": "1.2.3" }\n');
  await tempDir.write('apps/cerberus/pyproject.toml', '[project]\nname = "zyplux-cerberus"\nversion = "2.3.4"\n');
  await tempDir.write('containers/ci/Containerfile', 'FROM scratch\nLABEL org.opencontainers.image.version="3.4.5"\n');

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

export const test = cliTest.extend<CzFixtures>({
  catalog: async ({ cz, logs, tempDir }, use) => {
    await use(createCatalog(cz, tempDir, logs));
  },
  cz: async ({}, use) => {
    await use(createCliRunner(runCz));
  },
  liveWorkspace: async ({}, use) => {
    await use(createLiveWorkspace());
  },
  registries: async ({ network }, use) => {
    await use(createRegistries(network));
  },
  release: async ({ registries, repo, shell }, use) => {
    await use(createRelease(repo, registries, shell));
  },
  repo: async ({ shell, tempDir }, use) => {
    await use(createRepo(shell, tempDir));
  },
});

export const targetsTest = test.extend<TargetsFixtures>({
  targets: [
    async ({ repo, tempDir }, use) => {
      repo.setRoot(tempDir.path);
      await use(await seedReleaseTargets(tempDir));
    },
    { auto: true },
  ],
});

export const tempCwdTest = test.extend<{ tempCwd: undefined }>({
  tempCwd: [
    async ({ tempDir }, use) => {
      const entryCwd = process.cwd();
      process.chdir(tempDir.path);
      try {
        await use(undefined);
      } finally {
        process.chdir(entryCwd);
      }
    },
    { auto: true },
  ],
});

export type { TempDir } from '@zyplux/tests-fixtures';
export { describe, expect } from 'vitest';
