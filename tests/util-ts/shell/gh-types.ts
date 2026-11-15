import { expectTypeOf } from 'vitest';

import type { Shell } from './shell.ts';

const RUN_ID = 123;

export const assertGhTypes = (shell: Shell) => {
  const readPr = () => shell.gh.pr.view({ json: ['number', 'isDraft'] });
  const listPrs = () => shell.gh.pr.list({ json: ['state'] });
  const readRepo = () => shell.gh.repo.view({ json: ['nameWithOwner'] });
  const listReleases = () => shell.gh.release.list({ json: ['tagName'] });
  const listRuns = () => shell.gh.run.list({ json: ['databaseId'] });
  const createRelease = () => shell.gh.release.create('v1');
  expectTypeOf(readPr).returns.resolves.toEqualTypeOf<{ isDraft: boolean; number: number }>();
  expectTypeOf(listPrs).returns.resolves.toEqualTypeOf<{ state: string }[]>();
  expectTypeOf(readRepo).returns.resolves.toEqualTypeOf<{ nameWithOwner: string }>();
  expectTypeOf(listReleases).returns.resolves.toEqualTypeOf<{ tagName: string }[]>();
  expectTypeOf(listRuns).returns.resolves.toEqualTypeOf<{ databaseId: number }[]>();
  expectTypeOf(createRelease).returns.toEqualTypeOf<Promise<void>>();
  expectTypeOf<{ json: ['status'] }>().not.toExtend<Parameters<typeof shell.gh.pr.view>[0]>();
  expectTypeOf<{ json: [] }>().not.toExtend<Parameters<typeof shell.gh.run.list>[0]>();
  expectTypeOf<{ json: string }>().not.toExtend<Parameters<typeof shell.gh.repo.view>[0]>();
  expectTypeOf<{ jq: string; json: ['state'] }>().not.toExtend<Parameters<typeof shell.gh.pr.list>[0]>();
  const readRun = () => shell.gh.run.view(RUN_ID, { json: ['status', 'conclusion'] });
  const readStatus = () => shell.gh.run.view(RUN_ID, { json: ['status'] });
  const readConclusion = () => shell.gh.run.view(RUN_ID, { json: ['conclusion'] });
  expectTypeOf(readRun).returns.resolves.toEqualTypeOf<{ conclusion: string; status: string }>();
  expectTypeOf(readStatus).returns.resolves.toEqualTypeOf<{ status: string }>();
  expectTypeOf(readConclusion).returns.resolves.toEqualTypeOf<{ conclusion: string }>();
  expectTypeOf<{ json: ['status'] }>().toExtend<Parameters<typeof shell.gh.run.view>[1]>();
  expectTypeOf<{ json: ['unknown'] }>().not.toExtend<Parameters<typeof shell.gh.run.view>[1]>();
  expectTypeOf<{ json: [] }>().not.toExtend<Parameters<typeof shell.gh.run.view>[1]>();
  expectTypeOf<{ jq: string; json: ['status'] }>().not.toExtend<Parameters<typeof shell.gh.run.view>[1]>();
  expectTypeOf<{ json: string }>().not.toExtend<Parameters<typeof shell.gh.run.view>[1]>();
  expectTypeOf<undefined>().not.toExtend<Parameters<typeof shell.gh.run.view>[1]>();
  expectTypeOf<[number]>().not.toExtend<Parameters<typeof shell.gh.run.view>>();
};
