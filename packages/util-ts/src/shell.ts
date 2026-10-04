import type { ZodObject, ZodRawShape, ZodType } from 'zod';

import type { GhPr, GhRelease, GhRepo, GhRun } from './contracts.ts';
import type { ExecPromise } from './exec.ts';

import { GhSchema } from './contracts.ts';
import { run } from './exec.ts';
import { parseJson } from './json.ts';

type ShArg = (number | string)[] | number | string | undefined;

const sh = (strings: TemplateStringsArray, ...values: ShArg[]) => {
  const argv: string[] = [];
  for (const [index, chunk] of strings.entries()) {
    for (const token of chunk.split(/\s+/)) {
      if (token.length > 0) argv.push(token);
    }
    if (index >= values.length) continue;
    const value = values[index];
    if (Array.isArray(value)) {
      for (const item of value) argv.push(String(item));
    } else if (value !== undefined) {
      argv.push(String(value));
    }
  }
  return run(argv);
};

type BranchFlags = { delete?: boolean; force?: boolean };

type CleanFlags = { dryRun?: boolean; protect?: string[] };

type CloneFlags = { branch?: string; depth?: number; singleBranch?: boolean };

type CommandOutput = Awaited<ExecPromise>;

type FlagValue = boolean | number | string | undefined;

type JsonFields<Field extends string> = { jq?: never; json: readonly [Field, ...Field[]] };

type PrCreateFlags = { base: string; body: string; draft?: boolean; title: string };

type PrListFlags<Field extends keyof GhPr> = JsonFields<Field> & {
  head?: string;
  state?: 'all' | 'closed' | 'merged' | 'open';
};

type PrMergeFlags = { auto?: boolean; deleteBranch?: boolean; squash?: boolean };

type PrReadyFlags = { undo?: boolean };

type PullFlags = { ffOnly?: boolean };

type PushFlags = { setUpstream?: boolean };

type ReleaseCreateFlags = { generateNotes?: boolean; target?: string; title?: string };

type ReleaseDeleteFlags = { cleanupTag?: boolean; yes?: boolean };

type RevParseFlags = { abbrevRef?: boolean };

type RunListFlags<Field extends keyof GhRun> = JsonFields<Field> & {
  branch?: string;
  event?: string;
  workflow?: string;
};

type StatusFlags = { porcelain?: boolean };

const toKebab = (name: string) => name.replaceAll(/[A-Z]/g, char => `-${char.toLowerCase()}`);

const flag = (name: string, value: FlagValue) => {
  if (value === undefined || value === false) return [];
  return value === true ? [`--${toKebab(name)}`] : [`--${toKebab(name)}`, String(value)];
};

const toArgs = (flags: Record<string, FlagValue>) =>
  Object.entries(flags).flatMap(([name, value]) => flag(name, value));

const pickFields = <Shape extends ZodRawShape>(schema: ZodObject<Shape>, fields: readonly (keyof Shape)[]) => {
  const mask: Parameters<typeof schema.pick>[0] = {};
  for (const field of fields) Object.assign(mask, { [field]: true });
  return schema.pick(mask);
};

const readGh = async <T>(argv: string[], schema: ZodType<T>) => {
  const response = await sh`gh ${argv}`.quiet();
  return parseJson(response.text(), schema);
};

const gh = {
  pr: {
    create: async (flags: PrCreateFlags) => {
      await sh`gh ${['pr', 'create', ...toArgs(flags)]}`;
    },
    disableAutoMerge: async () => {
      await sh`gh pr merge --disable-auto`.nothrow().quiet();
    },
    list: async <Field extends keyof GhPr>({ json, ...flags }: PrListFlags<Field>): Promise<Pick<GhPr, Field>[]> =>
      readGh(['pr', 'list', ...toArgs(flags), '--json', json.join(',')], pickFields(GhSchema.pr, json).array()),
    merge: async (flags: PrMergeFlags = {}) => {
      await sh`gh ${['pr', 'merge', ...toArgs(flags)]}`;
    },
    ready: async (flags: PrReadyFlags = {}) => {
      await sh`gh ${['pr', 'ready', ...toArgs(flags)]}`;
    },
    reviews: async (slug: string, number: number) =>
      readGh(['api', `repos/${slug}/pulls/${number}/reviews?per_page=100`], GhSchema.reviews),
    view: async <Field extends keyof GhPr>({ json }: JsonFields<Field>): Promise<Pick<GhPr, Field>> =>
      readGh(['pr', 'view', '--json', json.join(',')], pickFields(GhSchema.pr, json)),
  },
  release: {
    create: async (tag: string, flags: ReleaseCreateFlags = {}) => {
      await sh`gh ${['release', 'create', tag, ...toArgs(flags)]}`;
    },
    delete: async (tag: string, flags: ReleaseDeleteFlags = {}) => {
      await sh`gh ${['release', 'delete', tag, ...toArgs(flags)]}`;
    },
    exists: async (tag: string) => {
      const query =
        'query($owner: String!, $name: String!, $tag: String!) { repository(owner: $owner, name: $name) { release(tagName: $tag) { id } } }';
      const { data } = await readGh(
        ['api', 'graphql', '-F', 'owner={owner}', '-F', 'name={repo}', '-f', `tag=${tag}`, '-f', `query=${query}`],
        GhSchema.releaseLookup,
      );
      return data.repository.release !== null;
    },
    list: async <Field extends keyof GhRelease>({ json }: JsonFields<Field>): Promise<Pick<GhRelease, Field>[]> =>
      readGh(['release', 'list', '--json', json.join(',')], pickFields(GhSchema.release, json).array()),
  },
  repo: {
    view: async <Field extends keyof GhRepo>({ json }: JsonFields<Field>): Promise<Pick<GhRepo, Field>> =>
      readGh(['repo', 'view', '--json', json.join(',')], pickFields(GhSchema.repo, json)),
  },
  run: {
    list: async <Field extends keyof GhRun>({ json, ...flags }: RunListFlags<Field>): Promise<Pick<GhRun, Field>[]> =>
      readGh(['run', 'list', ...toArgs(flags), '--json', json.join(',')], pickFields(GhSchema.run, json).array()),
    view: async <Field extends keyof GhRun>(runId: number, { json }: JsonFields<Field>): Promise<Pick<GhRun, Field>> =>
      readGh(['run', 'view', String(runId), '--json', json.join(',')], pickFields(GhSchema.run, json)),
  },
};

const git = {
  branch: async (name: string, flags: BranchFlags = {}) => sh`git ${['branch', ...toArgs(flags), name]}`,
  checkout: async (ref: string) => sh`git ${['checkout', ref]}`,
  clean: async (cwd: string, { dryRun = false, protect = [] }: CleanFlags = {}) =>
    sh`git ${['clean', '-d', '-f', '-f', '-X', ...(dryRun ? ['-n'] : []), ...protect.flatMap(pattern => ['-e', `!${pattern}`])]}`
      .cwd(cwd)
      .quiet(),
  clone: async (url: string, dest: string, flags: CloneFlags = {}) => sh`git ${['clone', ...toArgs(flags), url, dest]}`,
  fetch: async (remote: string, branch: string) => sh`git ${['fetch', remote, branch]}`,
  isInsideWorkTree: async (cwd: string) => sh`git ${['rev-parse', '--is-inside-work-tree']}`.cwd(cwd).quiet().nothrow(),
  lsFiles: async (cwd: string, pathspec: string[] = ['.']) =>
    sh`git ${['ls-files', '-z', '--', ...pathspec]}`.cwd(cwd).quiet(),
  lsRemote: async (remote: string, ref: string) => sh`git ${['ls-remote', remote, ref]}`.quiet(),
  pull: async (flags: PullFlags = {}) => sh`git ${['pull', ...toArgs(flags)]}`,
  push: async (remote: string, branch: string, flags: PushFlags = {}) =>
    sh`git ${['push', ...toArgs(flags), remote, branch]}`,
  revParse: async (rev: string, flags: RevParseFlags = {}) => sh`git ${['rev-parse', ...toArgs(flags), rev]}`.quiet(),
  showToplevel: async (cwd: string = process.cwd()) => sh`git ${['rev-parse', '--show-toplevel']}`.cwd(cwd).quiet(),
  status: async (flags: StatusFlags = {}) => sh`git ${['status', ...toArgs(flags)]}`,
};

export const $ = Object.assign(sh, { gh, git });

export const captureMerged = (argv: string[], env?: Record<string, string | undefined>): ExecPromise => {
  const merged = run(argv, { merge: true }).nothrow().quiet();
  return env === undefined ? merged : merged.env(env);
};

export const readTrimmed = async (command: Promise<CommandOutput>) => {
  const output = await command;
  return output.text().trim();
};
