export const ensure = (condition: boolean, message: string) => {
  if (!condition) {
    throw new Error(message);
  }
};

const readTrimmed = async (output: Promise<string>) => {
  const text = await output;
  return text.trim();
};

export const poll = async <T>(probe: () => Promise<T | undefined>, attempts: number, intervalMs: number) => {
  for (let attempt = 0; attempt < attempts; attempt++) {
    const found = await probe();
    if (found !== undefined) {
      return found;
    }
    await Bun.sleep(intervalMs);
  }
  return;
};

const bun = {
  pm: {
    view: (spec: string) => readTrimmed(Bun.$`bun pm view ${spec}`.nothrow().text()),
  },
};

const gh = {
  release: {
    create: (tag: string, options: { target: string }) =>
      Bun.$`gh release create ${tag} --target ${options.target} --title ${tag} --generate-notes`,
    view: async (tag: string) => {
      const result = await Bun.$`gh release view ${tag}`.quiet().nothrow();
      return result.exitCode === 0;
    },
  },
  run: {
    find: async (options: { event: string; headSha: string; workflow: string }) => {
      const query = `[.[] | select(.headSha=="${options.headSha}")][0].databaseId`;
      const id = await readTrimmed(
        Bun.$`gh run list --workflow=${options.workflow} --event=${options.event} --json databaseId,headSha --jq ${query}`
          .nothrow()
          .text(),
      );
      return id && id !== 'null' ? id : undefined;
    },
    watch: (runId: string) => Bun.$`gh run watch ${runId} --exit-status`,
  },
};

const git = {
  currentBranch: () => readTrimmed(Bun.$`git rev-parse --abbrev-ref HEAD`.text()),
  fetch: (remote: string, branch: string) => Bun.$`git fetch --quiet ${remote} ${branch}`,
  revParse: (rev: string) => readTrimmed(Bun.$`git rev-parse ${rev}`.text()),
  status: () => readTrimmed(Bun.$`git status --porcelain`.text()),
};

export const $ = Object.assign(Bun.$, { bun, gh, git });
