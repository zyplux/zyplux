import type { VersionSource } from '@zyplux/cz/contracts';
import type { CliRunner, ConsoleCapture, FetchFake, ShellFake, TempDir } from '@zyplux/tests-fixtures';

import { runCz } from '@zyplux/cz';
import { ManifestSchema } from '@zyplux/cz/contracts';
import { cliTest, createCliRunner, notFoundResponse, okResponse } from '@zyplux/tests-fixtures';
import { parseJson, parseToml, readJson } from '@zyplux/util';
import { execFileSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import * as z from 'zod';

export const workspaceRoot = fileURLToPath(new URL('../../', import.meta.url));

type Catalog = {
  loadRepos: () => Promise<string[]>;
  run: (options?: RunCatalogOptions) => Promise<void>;
  runOverWorkspace: () => Promise<void>;
  unresolvedNames: (system: 'npm' | 'pypi') => string[];
  writeManifest: (relativePath: string, content: string) => Promise<void>;
};

type CzFixtures = {
  catalog: Catalog;
  cz: CliRunner;
  findTarget: FindTarget;
  registries: Registries;
  release: Release;
  repo: Repo;
};

type FindTarget = (label: string) => Promise<TargetFacts>;

type PendingCerberusOptions = {
  published?: Partial<RegistryPublishedState>;
  tagRunPolls?: [string, ...string[]];
};

type Registries = { setPublished: (published: RegistryPublishedState) => void };

type RegistryPublishedState = {
  ghcrEverVisible?: boolean;
  ghcrPublished: boolean;
  npmPublished: boolean;
  pypiEverVisible?: boolean;
  pypiPublished: boolean;
};

type Release = {
  stagePendingCerberus: (options?: PendingCerberusOptions) => Promise<TargetFacts>;
  stagePendingCerberusAndCiImage: () => Promise<{ cerberus: TargetFacts; ciImage: TargetFacts }>;
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

type TargetFacts = { dir: string; version: string };

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

const CatalogSchema = z.array(z.string());

const createCatalog = (cz: CliRunner, tempDir: TempDir, { logLines }: ConsoleCapture) => {
  const outPath = path.join(tempDir.path, 'catalog.json');
  const runGit = (...args: string[]) => {
    execFileSync('git', args, { cwd: tempDir.path, stdio: 'ignore' });
  };
  runGit('init', '--quiet');

  return {
    loadRepos: async () => parseJson(await readFile(outPath, 'utf8'), CatalogSchema),
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

const readSourceVersion = async (source: VersionSource) => {
  const sourcePath = path.join(workspaceRoot, source.file);
  if ('json' in source) {
    const fields = await readJson(sourcePath, z.record(z.string(), z.unknown()));
    return z.string().parse(fields[source.json]);
  }
  const match = new RegExp(source.regex, 'm').exec(await readFile(sourcePath, 'utf8'))?.[1];
  if (match === undefined) throw new Error(`could not read version from ${source.file}`);
  return match;
};

const findTargetFacts = async (label: string) => {
  const manifestText = await readFile(path.join(workspaceRoot, 'release-targets.toml'), 'utf8');
  const manifest = parseToml(manifestText, ManifestSchema);
  const target = manifest.target.find(candidate => candidate.label === label);
  if (target === undefined) throw new Error(`${label} target missing from release-targets.toml`);
  return {
    dir: path.join(workspaceRoot, path.dirname(target.version.file)),
    version: await readSourceVersion(target.version),
  };
};

const createRepo = (shell: ShellFake) => {
  const setRoot = (dir: string) => {
    shell.on('git rev-parse --show-toplevel', dir);
  };
  setRoot(workspaceRoot);
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
    stagePendingCerberus: async ({ published, tagRunPolls = ['100\n101\n999'] }: PendingCerberusOptions = {}) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: false, ...published });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100\n101');
      shell.on(TAG_RUNS_PATTERN, ...tagRunPolls);
      return findTargetFacts('zyplux-cerberus');
    },
    stagePendingCerberusAndCiImage: async () => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: false, npmPublished: true, pypiPublished: false });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100');
      shell.on(/gh run list.*cerberus-v/, '100\n111');
      shell.on(/gh run list.*ci-image-v/, '100\n222');
      return {
        cerberus: await findTargetFacts('zyplux-cerberus'),
        ciImage: await findTargetFacts('ghcr.io/zyplux/ci'),
      };
    },
  }) satisfies Release;

const createRegistries = (network: FetchFake) =>
  ({
    setPublished: ({ ghcrEverVisible, ghcrPublished, npmPublished, pypiEverVisible, pypiPublished }) => {
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

export const test = cliTest.extend<CzFixtures>({
  catalog: async ({ cz, logs, tempDir }, use) => {
    await use(createCatalog(cz, tempDir, logs));
  },
  cz: async ({}, use) => {
    await use(createCliRunner(runCz));
  },
  findTarget: async ({}, use) => {
    await use(findTargetFacts);
  },
  registries: async ({ network }, use) => {
    await use(createRegistries(network));
  },
  release: async ({ registries, repo, shell }, use) => {
    await use(createRelease(repo, registries, shell));
  },
  repo: async ({ shell }, use) => {
    await use(createRepo(shell));
  },
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

export { notFoundResponse, okResponse } from '@zyplux/tests-fixtures';
export type { TempDir } from '@zyplux/tests-fixtures';
export { describe, expect, vi } from 'vitest';
