import type { ShellFake, TempDir } from '@zyplux/spectra';

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
