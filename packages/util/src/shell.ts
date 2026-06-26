type ApiFlags = { input?: string; jq?: string; method?: string; paginate?: boolean };

type BranchFlags = { delete?: boolean; force?: boolean };

type CloneFlags = { branch?: string; depth?: number; singleBranch?: boolean };

type CommandOutput = { text: () => string };

type FlagValue = boolean | number | string | undefined;

type PrCreateFlags = { base: string; body: string; draft?: boolean; title: string };

type PrListFlags = { head?: string; jq?: string; json?: string; state?: string };

type PrMergeFlags = { auto?: boolean; deleteBranch?: boolean; squash?: boolean };

type PrViewFlags = { jq?: string; json?: string };

type PullFlags = { ffOnly?: boolean };

type PushFlags = { setUpstream?: boolean };

type ReleaseCreateFlags = { generateNotes?: boolean; target?: string; title?: string };

type ReleaseListFlags = { jq?: string; json?: string };

type RevParseFlags = { abbrevRef?: boolean };

type RunListFlags = { event?: string; jq?: string; json?: string; workflow?: string };

type RunWatchFlags = { exitStatus?: boolean };

type StatusFlags = { porcelain?: boolean };

const toKebab = (name: string) => name.replaceAll(/[A-Z]/g, char => `-${char.toLowerCase()}`);

const flag = (name: string, value: FlagValue) => {
  if (value === undefined || value === false) return [];
  if (value === true) return [`--${toKebab(name)}`];
  return [`--${toKebab(name)}`, String(value)];
};

const toArgs = (flags: Record<string, FlagValue>) =>
  Object.entries(flags).flatMap(([name, value]) => flag(name, value));

const gh = {
  api: async (endpoint: string, flags: ApiFlags = {}) => Bun.$`gh ${['api', ...toArgs(flags), endpoint]}`.quiet(),
  pr: {
    create: async (flags: PrCreateFlags) => Bun.$`gh ${['pr', 'create', ...toArgs(flags)]}`,
    list: async (flags: PrListFlags = {}) => Bun.$`gh ${['pr', 'list', ...toArgs(flags)]}`,
    merge: async (flags: PrMergeFlags = {}) => Bun.$`gh ${['pr', 'merge', ...toArgs(flags)]}`,
    ready: async () => Bun.$`gh ${['pr', 'ready']}`,
    view: async (flags: PrViewFlags = {}) => Bun.$`gh ${['pr', 'view', ...toArgs(flags)]}`,
  },
  release: {
    create: async (tag: string, flags: ReleaseCreateFlags = {}) =>
      Bun.$`gh ${['release', 'create', tag, ...toArgs(flags)]}`,
    list: async (flags: ReleaseListFlags = {}) => Bun.$`gh ${['release', 'list', ...toArgs(flags)]}`,
  },
  run: {
    list: async (flags: RunListFlags = {}) => Bun.$`gh ${['run', 'list', ...toArgs(flags)]}`,
    watch: async (runId: string, flags: RunWatchFlags = {}) => Bun.$`gh ${['run', 'watch', runId, ...toArgs(flags)]}`,
  },
};

const git = {
  branch: async (name: string, flags: BranchFlags = {}) => Bun.$`git ${['branch', ...toArgs(flags), name]}`,
  checkout: async (ref: string) => Bun.$`git ${['checkout', ref]}`,
  clone: async (url: string, dest: string, flags: CloneFlags = {}) =>
    Bun.$`git ${['clone', ...toArgs(flags), url, dest]}`,
  fetch: async (remote: string, branch: string) => Bun.$`git ${['fetch', remote, branch]}`,
  isInsideWorkTree: async (cwd: string) =>
    Bun.$`git ${['rev-parse', '--is-inside-work-tree']}`.cwd(cwd).quiet().nothrow(),
  lsFiles: async (cwd: string, pathspec: string[] = ['.']) =>
    Bun.$`git ${['ls-files', '-z', '--', ...pathspec]}`.cwd(cwd).quiet(),
  pull: async (flags: PullFlags = {}) => Bun.$`git ${['pull', ...toArgs(flags)]}`,
  push: async (remote: string, branch: string, flags: PushFlags = {}) =>
    Bun.$`git ${['push', ...toArgs(flags), remote, branch]}`,
  revParse: async (rev: string, flags: RevParseFlags = {}) => Bun.$`git ${['rev-parse', ...toArgs(flags), rev]}`,
  showToplevel: async (cwd: string = process.cwd()) => Bun.$`git ${['rev-parse', '--show-toplevel']}`.cwd(cwd).quiet(),
  status: async (flags: StatusFlags = {}) => Bun.$`git ${['status', ...toArgs(flags)]}`,
};

export const $ = Object.assign(async (...args: Parameters<typeof Bun.$>) => Bun.$(...args), { gh, git });

export const readTrimmed = async (command: Promise<CommandOutput>) => {
  const output = await command;
  return output.text().trim();
};
