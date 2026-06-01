const readTrimmed = async (output: Promise<string>) => {
  const text = await output;
  return text.trim();
};

const gh = {
  pr: {
    create: (base: string, title: string) => Bun.$`gh pr create --base ${base} --title ${title} --body ${''} --draft`,
    isDraft: async () => (await readTrimmed(Bun.$`gh pr view --json isDraft --jq .isDraft`.text())) === 'true',
    merge: () => Bun.$`gh pr merge --squash --delete-branch`,
    mergeAuto: () => Bun.$`gh pr merge --auto --squash --delete-branch`,
    mergeState: () => readTrimmed(Bun.$`gh pr view --json mergeStateStatus --jq .mergeStateStatus`.text()),
    ready: () => Bun.$`gh pr ready`,
    state: (branch: string) =>
      readTrimmed(Bun.$`gh pr list --head ${branch} --state all --json state --jq ${'.[0].state // ""'}`.text()),
    url: () => readTrimmed(Bun.$`gh pr view --json url --jq .url`.text()),
  },
  release: {
    create: (tag: string, options: { target: string }) =>
      Bun.$`gh release create ${tag} --target ${options.target} --title ${tag} --generate-notes`,
    exists: async (tag: string) =>
      (await readTrimmed(Bun.$`gh release list --json tagName --jq ${`any(.[]; .tagName == "${tag}")`}`.text())) ===
      'true',
  },
  run: {
    find: async (options: { event: string; headSha: string; workflow: string }) => {
      const query = `[.[] | select(.headSha=="${options.headSha}")][0].databaseId`;
      const id = await readTrimmed(
        Bun.$`gh run list --workflow=${options.workflow} --event=${options.event} --json databaseId,headSha --jq ${query}`.text(),
      );
      return id && id !== 'null' ? id : undefined;
    },
    watch: (runId: string) => Bun.$`gh run watch ${runId} --exit-status`,
  },
};

const git = {
  checkout: (ref: string) => Bun.$`git checkout ${ref}`,
  currentBranch: () => readTrimmed(Bun.$`git rev-parse --abbrev-ref HEAD`.text()),
  deleteBranch: (branch: string) => Bun.$`git branch -D ${branch}`,
  fetch: (remote: string, branch: string) => Bun.$`git fetch ${remote} ${branch}`,
  pull: () => Bun.$`git pull --ff-only`,
  push: (remote: string, branch: string) => Bun.$`git push -u ${remote} ${branch}`,
  revParse: (rev: string) => readTrimmed(Bun.$`git rev-parse ${rev}`.text()),
  status: () => readTrimmed(Bun.$`git status --porcelain`.text()),
};

export const $ = Object.assign(Bun.$, { gh, git });
