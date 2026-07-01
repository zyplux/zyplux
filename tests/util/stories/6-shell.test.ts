import { fakeShellOutput, fakeShellPromise, toArgv } from '@zyplux/tests-shell-fixtures';
import { $, readTrimmed } from '@zyplux/util/shell';
import { test as base, describe, expect, vi } from 'vitest';

type CapturedCall = { argv: string[]; program: string };

const stubBunDollar = (calls: CapturedCall[]) => {
  const shellFn = vi.fn<typeof Bun.$>();
  shellFn.mockImplementation((strings, ...values) => {
    calls.push({ argv: toArgv(values), program: strings[0]?.trim() ?? '' });
    return fakeShellPromise(fakeShellOutput('output'));
  });
  return shellFn;
};

const test = base.extend<{ shellCalls: CapturedCall[] }>({
  shellCalls: async ({}, use) => {
    const calls: CapturedCall[] = [];
    const original = Bun.$;
    Bun.$ = stubBunDollar(calls);
    try {
      await use(calls);
    } finally {
      Bun.$ = original;
    }
  },
});

describe('6.1 translating flag objects into CLI arguments', () => {
  test('6.1.1 renders a true boolean flag as a bare kebab-case switch', async ({ shellCalls }) => {
    await $.git.pull({ ffOnly: true });
    expect(shellCalls[0]).toEqual({ argv: ['pull', '--ff-only'], program: 'git' });
  });

  test('6.1.2 omits a false boolean flag entirely', async ({ shellCalls }) => {
    await $.git.branch('feat-x', { delete: false });
    expect(shellCalls[0]).toEqual({ argv: ['branch', 'feat-x'], program: 'git' });
  });

  test('6.1.3 renders a valued flag as a switch followed by its stringified value', async ({ shellCalls }) => {
    await $.gh.run.view('123', { json: 'status,conclusion' });
    expect(shellCalls[0]).toEqual({ argv: ['run', 'view', '123', '--json', 'status,conclusion'], program: 'gh' });
  });

  test('6.1.4 renders every own flag in a multi-flag object', async ({ shellCalls }) => {
    await $.gh.pr.list({ head: 'my-branch', jq: '.x', json: 'state', state: 'all' });
    expect(shellCalls[0]).toEqual({
      argv: ['pr', 'list', '--head', 'my-branch', '--jq', '.x', '--json', 'state', '--state', 'all'],
      program: 'gh',
    });
  });
});

describe('6.2 building git subcommands', () => {
  test.each([
    [
      'branch',
      () => $.git.branch('feat-x', { delete: true, force: true }),
      ['branch', '--delete', '--force', 'feat-x'],
    ],
    ['checkout', () => $.git.checkout('main'), ['checkout', 'main']],
    [
      'clone',
      () => $.git.clone('https://example.com/x.git', 'dest', { depth: 1, singleBranch: true }),
      ['clone', '--depth', '1', '--single-branch', 'https://example.com/x.git', 'dest'],
    ],
    ['fetch', () => $.git.fetch('origin', 'main'), ['fetch', 'origin', 'main']],
    ['isInsideWorkTree', () => $.git.isInsideWorkTree('/tmp'), ['rev-parse', '--is-inside-work-tree']],
    ['lsFiles default pathspec', () => $.git.lsFiles('/repo'), ['ls-files', '-z', '--', '.']],
    ['lsFiles explicit pathspec', () => $.git.lsFiles('/repo', ['a', 'b']), ['ls-files', '-z', '--', 'a', 'b']],
    ['lsRemote', () => $.git.lsRemote('origin', 'refs/heads/main'), ['ls-remote', 'origin', 'refs/heads/main']],
    ['pull with flags', () => $.git.pull({ ffOnly: true }), ['pull', '--ff-only']],
    ['pull without flags', () => $.git.pull(), ['pull']],
    ['push', () => $.git.push('origin', 'main', { setUpstream: true }), ['push', '--set-upstream', 'origin', 'main']],
    ['revParse', () => $.git.revParse('HEAD', { abbrevRef: true }), ['rev-parse', '--abbrev-ref', 'HEAD']],
    ['showToplevel', () => $.git.showToplevel('/tmp'), ['rev-parse', '--show-toplevel']],
    ['status', () => $.git.status({ porcelain: true }), ['status', '--porcelain']],
  ] as const)('6.2.1 builds git %s argv from its arguments and flags', async (_name, invoke, expectedArgv) => {
    const calls: CapturedCall[] = [];
    const original = Bun.$;
    Bun.$ = stubBunDollar(calls);

    try {
      await invoke();
      expect(calls[0]).toEqual({ argv: [...expectedArgv], program: 'git' });
    } finally {
      Bun.$ = original;
    }
  });
});

describe('6.3 building gh subcommands', () => {
  test.each([
    [
      'api',
      () => $.gh.api('repos/x/y', { input: '-', method: 'POST' }),
      ['api', '--input', '-', '--method', 'POST', 'repos/x/y'],
    ],
    [
      'pr create',
      () => $.gh.pr.create({ base: 'main', body: '', draft: true, title: 't' }),
      ['pr', 'create', '--base', 'main', '--body', '', '--draft', '--title', 't'],
    ],
    ['pr disableAutoMerge', () => $.gh.pr.disableAutoMerge(), ['pr', 'merge', '--disable-auto']],
    ['pr list', () => $.gh.pr.list({ head: 'b', json: 'state' }), ['pr', 'list', '--head', 'b', '--json', 'state']],
    [
      'pr merge',
      () => $.gh.pr.merge({ auto: true, deleteBranch: true, squash: true }),
      ['pr', 'merge', '--auto', '--delete-branch', '--squash'],
    ],
    ['pr ready with flags', () => $.gh.pr.ready({ undo: true }), ['pr', 'ready', '--undo']],
    ['pr ready without flags', () => $.gh.pr.ready(), ['pr', 'ready']],
    ['pr view', () => $.gh.pr.view({ json: 'url' }), ['pr', 'view', '--json', 'url']],
    [
      'release create',
      () => $.gh.release.create('v1.0.0', { generateNotes: true, target: 'sha', title: 'v1.0.0' }),
      ['release', 'create', 'v1.0.0', '--generate-notes', '--target', 'sha', '--title', 'v1.0.0'],
    ],
    ['release list', () => $.gh.release.list({ json: 'tagName' }), ['release', 'list', '--json', 'tagName']],
    ['repo view', () => $.gh.repo.view({ json: 'nameWithOwner' }), ['repo', 'view', '--json', 'nameWithOwner']],
    [
      'run list',
      () => $.gh.run.list({ event: 'release', workflow: 'release.yml' }),
      ['run', 'list', '--event', 'release', '--workflow', 'release.yml'],
    ],
    [
      'run view',
      () => $.gh.run.view('123', { json: 'status,conclusion' }),
      ['run', 'view', '123', '--json', 'status,conclusion'],
    ],
  ] as const)('6.3.1 builds gh %s argv from its arguments and flags', async (_name, invoke, expectedArgv) => {
    const calls: CapturedCall[] = [];
    const original = Bun.$;
    Bun.$ = stubBunDollar(calls);

    try {
      await invoke();
      expect(calls[0]).toEqual({ argv: [...expectedArgv], program: 'gh' });
    } finally {
      Bun.$ = original;
    }
  });
});

describe('6.4 reading trimmed command output', () => {
  test('6.4.1 awaits a command and trims its text output', async () => {
    const command = Promise.resolve({ text: () => '  hello  \n' });
    expect(await readTrimmed(command)).toBe('hello');
  });
});

describe('6.5 invoking the shell function directly', () => {
  test('6.5.1 forwards a direct call to the underlying Bun.$ tagged template', async () => {
    const calls: { strings: readonly string[]; values: unknown[] }[] = [];
    const original = Bun.$;
    const shellFn = vi.fn<typeof Bun.$>();
    shellFn.mockImplementation((strings, ...values) => {
      calls.push({ strings: [...strings], values });
      return fakeShellPromise(fakeShellOutput('output'));
    });
    Bun.$ = shellFn;

    try {
      const dir = '/tmp/pkg';
      await $`cd ${dir} && echo hi`;
      expect(calls[0]).toEqual({ strings: ['cd ', ' && echo hi'], values: [dir] });
    } finally {
      Bun.$ = original;
    }
  });
});

describe('6.6 omitting optional flags falls back to defaults', () => {
  test.each([
    ['gh.api', () => $.gh.api('repos/x/y'), ['api', 'repos/x/y'], 'gh'],
    ['gh.pr.list', () => $.gh.pr.list(), ['pr', 'list'], 'gh'],
    ['gh.pr.merge', () => $.gh.pr.merge(), ['pr', 'merge'], 'gh'],
    ['gh.pr.view', () => $.gh.pr.view(), ['pr', 'view'], 'gh'],
    ['gh.release.create', () => $.gh.release.create('v1.0.0'), ['release', 'create', 'v1.0.0'], 'gh'],
    ['gh.release.list', () => $.gh.release.list(), ['release', 'list'], 'gh'],
    ['gh.repo.view', () => $.gh.repo.view(), ['repo', 'view'], 'gh'],
    ['gh.run.list', () => $.gh.run.list(), ['run', 'list'], 'gh'],
    ['gh.run.view', () => $.gh.run.view('123'), ['run', 'view', '123'], 'gh'],
    ['git.branch', () => $.git.branch('feat-x'), ['branch', 'feat-x'], 'git'],
    ['git.clone', () => $.git.clone('url', 'dest'), ['clone', 'url', 'dest'], 'git'],
    ['git.push', () => $.git.push('origin', 'main'), ['push', 'origin', 'main'], 'git'],
    ['git.revParse', () => $.git.revParse('HEAD'), ['rev-parse', 'HEAD'], 'git'],
    ['git.status', () => $.git.status(), ['status'], 'git'],
  ] as const)(
    '6.6.1 omits any flags when %s is called without them',
    async (_name, invoke, expectedArgv, expectedProgram) => {
      const calls: CapturedCall[] = [];
      const original = Bun.$;
      Bun.$ = stubBunDollar(calls);

      try {
        await invoke();
        expect(calls[0]).toEqual({ argv: [...expectedArgv], program: expectedProgram });
      } finally {
        Bun.$ = original;
      }
    },
  );

  test('6.6.2 defaults cwd to process.cwd() when git.showToplevel is called without it', async ({ shellCalls }) => {
    await $.git.showToplevel();
    expect(shellCalls[0]).toEqual({ argv: ['rev-parse', '--show-toplevel'], program: 'git' });
  });
});
