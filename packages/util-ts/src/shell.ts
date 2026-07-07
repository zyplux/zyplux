type ApiFlags = { input?: string; jq?: string; method?: string; paginate?: boolean };

type BranchFlags = { delete?: boolean; force?: boolean };

type CleanFlags = { dryRun?: boolean; protect?: string[] };

type CloneFlags = { branch?: string; depth?: number; singleBranch?: boolean };

type CommandOutput = { text: () => string };

type FlagValue = boolean | number | string | undefined;

type PrCreateFlags = { base: string; body: string; draft?: boolean; title: string };

type PrListFlags = { head?: string; jq?: string; json?: string; state?: string };

type PrMergeFlags = { auto?: boolean; deleteBranch?: boolean; squash?: boolean };

type PrReadyFlags = { undo?: boolean };

type PrViewFlags = { jq?: string; json?: string };

type PullFlags = { ffOnly?: boolean };

type PushFlags = { setUpstream?: boolean };

type ReleaseCreateFlags = { generateNotes?: boolean; target?: string; title?: string };

type ReleaseListFlags = { jq?: string; json?: string };

type RepoViewFlags = { jq?: string; json?: string };

type RevParseFlags = { abbrevRef?: boolean };

type RunListFlags = { event?: string; jq?: string; json?: string; workflow?: string };

type RunViewFlags = { jq?: string; json?: string };

type StatusFlags = { porcelain?: boolean };

const toKebab = (name: string) => name.replaceAll(/[A-Z]/g, char => `-${char.toLowerCase()}`);

const flag = (name: string, value: FlagValue) => {
  if (value === undefined || value === false) return [];
  if (value === true) return [`--${toKebab(name)}`];
  return [`--${toKebab(name)}`, String(value)];
};

const toArgs = (flags: Record<string, FlagValue>) => Object.entries(flags).flatMap(([name, value]) => flag(name, value));

const gh = {
  api: async (endpoint: string, flags: ApiFlags = {}) => Bun.$`gh ${['api', ...toArgs(flags), endpoint]}`.quiet(),
  pr: {
    create: async (flags: PrCreateFlags) => Bun.$`gh ${['pr', 'create', ...toArgs(flags)]}`,
    disableAutoMerge: async () => Bun.$`gh ${['pr', 'merge', '--disable-auto']}`.nothrow().quiet(),
    list: async (flags: PrListFlags = {}) => Bun.$`gh ${['pr', 'list', ...toArgs(flags)]}`.quiet(),
    merge: async (flags: PrMergeFlags = {}) => Bun.$`gh ${['pr', 'merge', ...toArgs(flags)]}`,
    ready: async (flags: PrReadyFlags = {}) => Bun.$`gh ${['pr', 'ready', ...toArgs(flags)]}`,
    view: async (flags: PrViewFlags = {}) => Bun.$`gh ${['pr', 'view', ...toArgs(flags)]}`.quiet(),
  },
  release: {
    create: async (tag: string, flags: ReleaseCreateFlags = {}) => Bun.$`gh ${['release', 'create', tag, ...toArgs(flags)]}`,
    list: async (flags: ReleaseListFlags = {}) => Bun.$`gh ${['release', 'list', ...toArgs(flags)]}`.quiet(),
  },
  repo: {
    view: async (flags: RepoViewFlags = {}) => Bun.$`gh ${['repo', 'view', ...toArgs(flags)]}`.quiet(),
  },
  run: {
    list: async (flags: RunListFlags = {}) => Bun.$`gh ${['run', 'list', ...toArgs(flags)]}`.quiet(),
    view: async (runId: string, flags: RunViewFlags = {}) => Bun.$`gh ${['run', 'view', runId, ...toArgs(flags)]}`.quiet(),
  },
};

const git = {
  branch: async (name: string, flags: BranchFlags = {}) => Bun.$`git ${['branch', ...toArgs(flags), name]}`,
  checkout: async (ref: string) => Bun.$`git ${['checkout', ref]}`,
  clean: async (cwd: string, { dryRun = false, protect = [] }: CleanFlags = {}) =>
    Bun.$`git ${['clean', '-d', '-f', '-f', '-X', ...(dryRun ? ['-n'] : []), ...protect.flatMap(pattern => ['-e', `!${pattern}`])]}`.cwd(cwd).quiet(),
  clone: async (url: string, dest: string, flags: CloneFlags = {}) => Bun.$`git ${['clone', ...toArgs(flags), url, dest]}`,
  fetch: async (remote: string, branch: string) => Bun.$`git ${['fetch', remote, branch]}`,
  isInsideWorkTree: async (cwd: string) => Bun.$`git ${['rev-parse', '--is-inside-work-tree']}`.cwd(cwd).quiet().nothrow(),
  lsFiles: async (cwd: string, pathspec: string[] = ['.']) => Bun.$`git ${['ls-files', '-z', '--', ...pathspec]}`.cwd(cwd).quiet(),
  lsRemote: async (remote: string, ref: string) => Bun.$`git ${['ls-remote', remote, ref]}`.quiet(),
  pull: async (flags: PullFlags = {}) => Bun.$`git ${['pull', ...toArgs(flags)]}`,
  push: async (remote: string, branch: string, flags: PushFlags = {}) => Bun.$`git ${['push', ...toArgs(flags), remote, branch]}`,
  revParse: async (rev: string, flags: RevParseFlags = {}) => Bun.$`git ${['rev-parse', ...toArgs(flags), rev]}`.quiet(),
  showToplevel: async (cwd: string = process.cwd()) => Bun.$`git ${['rev-parse', '--show-toplevel']}`.cwd(cwd).quiet(),
  status: async (flags: StatusFlags = {}) => Bun.$`git ${['status', ...toArgs(flags)]}`,
};

export const $ = Object.assign(async (...args: Parameters<typeof Bun.$>) => Bun.$(...args), { gh, git });

export const readTrimmed = async (command: Promise<CommandOutput>) => {
  const output = await command;
  return output.text().trim();
};
