import type { FetchFake } from '@zyplux/tests-fixtures/fetch';
import type { TempDir } from '@zyplux/tests-fixtures/fs';
import type { ShellFake } from '@zyplux/tests-fixtures/shell';

import { ManifestSchema } from '@zyplux/cz/contracts';
import { notFoundResponse, okResponse } from '@zyplux/tests-fixtures/fetch';
import { parseToml } from '@zyplux/util';
import { execFileSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const workspaceRoot = fileURLToPath(new URL('../../../', import.meta.url));

export type LiveWorkspace = {
  root: string;
  targetLabels: () => Promise<string[]>;
};

export type PendingCerberusOptions = {
  published?: RegistryPublishedState;
  tagRunPolls?: [string[], ...string[][]];
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

export type Repo = {
  queuePrFields: (
    fields: Record<string, [boolean | number | string, ...(boolean | number | string)[]] | boolean | number | string>,
  ) => void;
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

export type SeededTargets = {
  cerberus: TargetFacts;
  ci: TargetFacts;
  util: TargetFacts;
};

export type UpgradeWorkspace = {
  readDockerfile: () => Promise<string>;
  stage: (options?: { nodeVersion?: string; python?: boolean; turbo?: boolean }) => Promise<void>;
  stubReleases: () => void;
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

export const createRepo = (shell: ShellFake, { path: tempPath }: TempDir) => {
  const setRoot = (dir: string) => {
    shell.on('git rev-parse --show-toplevel', dir);
  };
  setRoot(tempPath);
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
        const [first, ...later] = Array.isArray(values) ? values : [values];
        shell.on(
          `gh pr view --json ${field}`,
          JSON.stringify({ [field]: first }),
          ...later.map(value => JSON.stringify({ [field]: value })),
        );
      }
    },
    setCopilotReviewedHead: sha => {
      shell.on(
        /^gh api repos\//,
        JSON.stringify([{ commit_id: sha, user: { login: 'copilot-pull-request-reviewer[bot]' } }]),
      );
    },
    setCurrentBranch,
    setHeadSha,
    setPrListState: state => {
      shell.on('gh pr list', JSON.stringify(state ? [{ state }] : []));
    },
    setRemoteBranchSha,
    setRemoteMainSha,
    setRepoSlug: slug => {
      shell.on('gh repo view --json nameWithOwner', JSON.stringify({ nameWithOwner: slug }));
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
        if (pypiProbeCount === 1) return pypiPublished ? okResponse() : notFoundResponse();
        return pypiEverVisible === false ? notFoundResponse() : okResponse();
      });
      network.on('https://registry.npmjs.org/', () => (npmPublished ? okResponse() : notFoundResponse()));
    },
  }) satisfies Registries;

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

const renderRunIds = (ids: string[]) => JSON.stringify(ids.map(id => ({ databaseId: Number(id) })));

const renderRun = ({ conclusion = '', status }: RunState) => JSON.stringify({ conclusion, status });

export const createRelease = (repo: Repo, registries: Registries, shell: ShellFake) => {
  const queueRun = (runId: string, first: RunState, ...later: RunState[]) => {
    shell.on(`gh run view ${runId}`, renderRun(first), ...later.map(run => renderRun(run)));
  };

  return {
    completeRunAfter: (runId, predecessorId, conclusion) => {
      let isPredecessorCompleted = false;
      shell.on(`gh run view ${predecessorId}`, () => {
        isPredecessorCompleted = true;
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

export const createLiveWorkspace = () =>
  ({
    root: workspaceRoot,
    targetLabels: async () => {
      const manifestText = await readFile(path.join(workspaceRoot, 'release-targets.toml'), 'utf8');
      return parseToml(manifestText, ManifestSchema).target.map(target => target.label);
    },
  }) satisfies LiveWorkspace;

export const enterCwd = (dir: string) => {
  const entryCwd = process.cwd();
  process.chdir(dir);
  return () => {
    process.chdir(entryCwd);
  };
};

export type InitRepo = (relativeDir: string, extraIgnored?: string[]) => Promise<void>;
export type WriteArtifacts = (relativeDir: string) => Promise<void>;

const runGit = (cwd: string, ...args: string[]) => {
  execFileSync('git', args, { cwd, stdio: 'ignore' });
};

export const createInitRepo =
  (tempDir: TempDir): InitRepo =>
  async (relativeDir, extraIgnored = []) => {
    const ignored = ['node_modules/', 'dist/', '.env', '.env.*', ...extraIgnored];
    await tempDir.write(path.join(relativeDir, '.gitignore'), `${ignored.join('\n')}\n`);
    const repoPath = path.join(tempDir.path, relativeDir);
    runGit(repoPath, 'init', '-q');
    runGit(repoPath, 'add', '.gitignore');
    runGit(repoPath, '-c', 'user.email=test@example.com', '-c', 'user.name=Test', 'commit', '-qm', 'init');
  };

export const createWriteArtifacts =
  (tempDir: TempDir): WriteArtifacts =>
  async relativeDir => {
    await tempDir.write(path.join(relativeDir, 'node_modules/pkg/index.js'), 'x');
    await tempDir.write(path.join(relativeDir, 'dist/out.js'), 'x');
    await tempDir.write(path.join(relativeDir, '.env'), 'SECRET=1');
  };
