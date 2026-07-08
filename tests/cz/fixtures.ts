import type { CliRunner, ConsoleCapture, FetchFake, ShellFake, TempDir } from '@zyplux/tests-fixtures';

import { readVersion, runCz, VersionSourceSchema } from '@zyplux/cz';
import { cliTest, createCliRunner, notFoundResponse, okResponse } from '@zyplux/tests-fixtures';
import { parseJson, parseToml } from '@zyplux/util';
import { execFileSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
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
  repo: Repo;
};

type FindTarget = (label: string) => Promise<TargetFacts>;

type Registries = { setPublished: (published: RegistryPublishedState) => void };

type RegistryPublishedState = {
  ghcrEverVisible?: boolean;
  ghcrPublished: boolean;
  npmPublished: boolean;
  pypiEverVisible?: boolean;
  pypiPublished: boolean;
};

type Repo = {
  queuePrField: (field: string, ...values: [string, ...string[]]) => void;
  setCopilotReviewedHead: (sha: string) => void;
  setCurrentBranch: (branch: string) => void;
  setHeadSha: (sha: string) => void;
  setPrListState: (state: string) => void;
  setRemoteBranchSha: (branch: string, ...shas: [string, ...string[]]) => void;
  setRemoteMainSha: (sha: string) => void;
  setRepoSlug: (slug: string) => void;
  setRoot: (dir: string) => void;
  setWorkingTreeStatus: (status: string) => void;
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

const TargetEntrySchema = z.object({ label: z.string(), version: VersionSourceSchema });
const TargetManifestSchema = z.object({ target: z.array(TargetEntrySchema) });

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

const findTargetFacts = async (label: string) => {
  const manifestText = await readFile(path.join(workspaceRoot, 'release-targets.toml'), 'utf8');
  const manifest = parseToml(manifestText, TargetManifestSchema);
  const target = manifest.target.find(candidate => candidate.label === label);
  if (target === undefined) throw new Error(`${label} target missing from release-targets.toml`);
  return {
    dir: path.join(workspaceRoot, path.dirname(target.version.file)),
    version: await readVersion(workspaceRoot, target.version),
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

  return {
    queuePrField: (field, ...values) => {
      shell.on(`gh pr view --jq .${field}`, ...values);
    },
    setCopilotReviewedHead: sha => {
      shell.on('gh api', sha);
    },
    setCurrentBranch,
    setHeadSha,
    setPrListState: state => {
      shell.on('gh pr list', state);
    },
    setRemoteBranchSha: (branch, ...shas) => {
      const [firstSha, ...laterShas] = shas;
      const toRefLine = (sha: string) => `${sha}\trefs/heads/${branch}`;
      shell.on(
        `git ls-remote origin refs/heads/${branch}`,
        toRefLine(firstSha),
        ...laterShas.map(sha => toRefLine(sha)),
      );
    },
    setRemoteMainSha,
    setRepoSlug: slug => {
      shell.on('gh repo view --jq .nameWithOwner', slug);
    },
    setRoot,
    setWorkingTreeStatus,
    syncMain: sha => {
      setCurrentBranch('main');
      setHeadSha(sha);
      setRemoteMainSha(sha);
      setWorkingTreeStatus('');
    },
  } satisfies Repo;
};

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
  repo: async ({ shell }, use) => {
    await use(createRepo(shell));
  },
});

export { notFoundResponse, okResponse } from '@zyplux/tests-fixtures';
export type { TempDir } from '@zyplux/tests-fixtures';
export { describe, expect, vi } from 'vitest';
