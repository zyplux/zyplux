import type { Shell, ShellFake } from '#fixtures';

import { describe, expect, test } from '#fixtures';

const RUN_ID = 123;

type ArgvCase = [string, Invoke, string[]];
type FlaglessArgvCase = [string, Invoke, string[], string];
type Invoke = ($: Shell) => Promise<unknown>;

const expectBuiltArgv = async (
  shell: ShellFake,
  invoke: () => Promise<unknown>,
  program: string,
  expectedArgv: readonly string[],
) => {
  shell.otherwise('output');

  await invoke();

  expect(shell.calls[0]).toMatchObject({ argv: [...expectedArgv], program });
};

describe('6.1 translating flag objects into CLI arguments', () => {
  test('6.1.1 omits a false boolean flag entirely', async ({ $, shell }) => {
    await expectBuiltArgv(shell, () => $.git.branch('feat-x', { delete: false }), 'git', ['branch', 'feat-x']);
  });
});

const gitArgvCases: ArgvCase[] = [
  ['branch', $ => $.git.branch('feat-x', { delete: true, force: true }), ['branch', '--delete', '--force', 'feat-x']],
  ['checkout', $ => $.git.checkout('main'), ['checkout', 'main']],
  [
    'clone',
    $ => $.git.clone('https://example.com/x.git', 'dest', { depth: 1, singleBranch: true }),
    ['clone', '--depth', '1', '--single-branch', 'https://example.com/x.git', 'dest'],
  ],
  ['fetch', $ => $.git.fetch('origin', 'main'), ['fetch', 'origin', 'main']],
  ['isInsideWorkTree', $ => $.git.isInsideWorkTree('/tmp'), ['rev-parse', '--is-inside-work-tree']],
  ['lsFiles default pathspec', $ => $.git.lsFiles('/repo'), ['ls-files', '-z', '--', '.']],
  ['lsFiles explicit pathspec', $ => $.git.lsFiles('/repo', ['a', 'b']), ['ls-files', '-z', '--', 'a', 'b']],
  ['lsRemote', $ => $.git.lsRemote('origin', 'refs/heads/main'), ['ls-remote', 'origin', 'refs/heads/main']],
  ['pull with flags', $ => $.git.pull({ ffOnly: true }), ['pull', '--ff-only']],
  ['pull without flags', $ => $.git.pull(), ['pull']],
  ['push', $ => $.git.push('origin', 'main', { setUpstream: true }), ['push', '--set-upstream', 'origin', 'main']],
  ['revParse', $ => $.git.revParse('HEAD', { abbrevRef: true }), ['rev-parse', '--abbrev-ref', 'HEAD']],
  ['showToplevel', $ => $.git.showToplevel('/tmp'), ['rev-parse', '--show-toplevel']],
  ['status', $ => $.git.status({ porcelain: true }), ['status', '--porcelain']],
];

describe('6.2 building git subcommands', () => {
  test.for(gitArgvCases)(
    '6.2.1 builds git %s argv from its arguments and flags',
    async ([, invoke, expectedArgv], { $, shell }) => expectBuiltArgv(shell, () => invoke($), 'git', expectedArgv),
  );
});

const ghArgvCases: ArgvCase[] = [
  [
    'pr create',
    $ => $.gh.pr.create({ base: 'main', body: '', draft: true, title: 't' }),
    ['pr', 'create', '--base', 'main', '--body', '', '--draft', '--title', 't'],
  ],
  ['pr disableAutoMerge', $ => $.gh.pr.disableAutoMerge(), ['pr', 'merge', '--disable-auto']],
  [
    'pr merge',
    $ => $.gh.pr.merge({ auto: true, deleteBranch: true, squash: true }),
    ['pr', 'merge', '--auto', '--delete-branch', '--squash'],
  ],
  ['pr ready with flags', $ => $.gh.pr.ready({ undo: true }), ['pr', 'ready', '--undo']],
  ['pr ready without flags', $ => $.gh.pr.ready(), ['pr', 'ready']],
  [
    'release create',
    $ => $.gh.release.create('v1.0.0', { generateNotes: true, target: 'sha', title: 'v1.0.0' }),
    ['release', 'create', 'v1.0.0', '--generate-notes', '--target', 'sha', '--title', 'v1.0.0'],
  ],
];

describe('6.3 building gh subcommands', () => {
  test.for(ghArgvCases)(
    '6.3.1 builds gh %s argv from its arguments and flags',
    async ([, invoke, expectedArgv], { $, shell }) => expectBuiltArgv(shell, () => invoke($), 'gh', expectedArgv),
  );
});

describe('6.4 reading trimmed command output', () => {
  test('6.4.1 awaits a command and trims its text output', async ({ $, readTrimmed, shell }) => {
    shell.otherwise('  abc123  \n');

    expect(await readTrimmed($.git.revParse('HEAD'))).toBe('abc123');
  });
});

describe('6.5 invoking the shell function directly', () => {
  test('6.5.1 forwards a direct call to the underlying shell harness', async ({ $, shell }) => {
    shell.otherwise('output');
    const dir = '/tmp/pkg';

    await $`cd ${dir} && echo hi`;

    expect(shell.commands[0]).toBe('cd /tmp/pkg && echo hi');
  });
});

const flaglessArgvCases: FlaglessArgvCase[] = [
  ['gh.pr.merge', $ => $.gh.pr.merge(), ['pr', 'merge'], 'gh'],
  ['gh.release.create', $ => $.gh.release.create('v1.0.0'), ['release', 'create', 'v1.0.0'], 'gh'],
  ['git.branch', $ => $.git.branch('feat-x'), ['branch', 'feat-x'], 'git'],
  ['git.clone', $ => $.git.clone('url', 'dest'), ['clone', 'url', 'dest'], 'git'],
  ['git.push', $ => $.git.push('origin', 'main'), ['push', 'origin', 'main'], 'git'],
  ['git.revParse', $ => $.git.revParse('HEAD'), ['rev-parse', 'HEAD'], 'git'],
  ['git.status', $ => $.git.status(), ['status'], 'git'],
];

describe('6.6 omitting optional flags falls back to defaults', () => {
  test.for(flaglessArgvCases)(
    '6.6.1 omits any flags when %s is called without them',
    async ([, invoke, expectedArgv, expectedProgram], { $, shell }) =>
      expectBuiltArgv(shell, () => invoke($), expectedProgram, expectedArgv),
  );

  test('6.6.2 builds the same show toplevel argv when git.showToplevel is called without a cwd', async ({
    $,
    shell,
  }) => {
    await expectBuiltArgv(shell, () => $.git.showToplevel(), 'git', ['rev-parse', '--show-toplevel']);
  });
});

describe('6.7 reading typed GitHub run fields', () => {
  test('6.7.1 returns selected fields as a typed object', async ({ $, shell }) => {
    shell.otherwise('{"status":"completed","conclusion":"success"}');
    const run = await $.gh.run.view(RUN_ID, { json: ['status', 'conclusion'] });
    expect(run).toEqual({ conclusion: 'success', status: 'completed' });
    expect(shell.calls[0]).toMatchObject({
      argv: ['run', 'view', '123', '--json', 'status,conclusion'],
      program: 'gh',
    });
  });

  test('6.7.2 validates and exposes only the selected fields', async ({ $, shell }) => {
    shell.otherwise('{"status":"queued","conclusion":42}');
    const run = await $.gh.run.view(RUN_ID, { json: ['status'] });
    expect(run).toEqual({ status: 'queued' });
    expect(shell.calls[0]).toMatchObject({ argv: ['run', 'view', '123', '--json', 'status'], program: 'gh' });
  });

  test('6.7.3 preserves an empty conclusion', async ({ $, shell }) => {
    shell.otherwise('{"conclusion":""}');
    const run = await $.gh.run.view(RUN_ID, { json: ['conclusion'] });
    expect(run).toEqual({ conclusion: '' });
  });

  test.for(['not JSON', '{}', '{"status":42}', '{"status":null}'])(
    '6.7.4 rejects invalid JSON or missing or invalid selected fields: %s',
    async (stdout, { $, shell }) => {
      shell.otherwise(stdout);
      await expect($.gh.run.view(RUN_ID, { json: ['status'] })).rejects.toThrow();
    },
  );

  test('6.7.5 propagates command failures before parsing stdout', async ({ $, shell }) => {
    shell.otherwise({ exitCode: 1, stdout: 'unavailable' });
    await expect($.gh.run.view(RUN_ID, { json: ['status'] })).rejects.toMatchObject({ exitCode: 1 });
  });

  test('6.7.6 infers selected fields and rejects invalid options at compile time', ({ $, assertGhTypes }) => {
    assertGhTypes($);
  });
});

type JsonCase = {
  argv: string[];
  expected: unknown;
  invalid: string;
  invoke: Invoke;
  name: string;
  stdout: string;
};

const jsonCases: JsonCase[] = [
  {
    argv: ['pr', 'view', '--json', 'isDraft,number'],
    expected: { isDraft: false, number: 7 },
    invalid: '{"isDraft":"false","number":7}',
    invoke: $ => $.gh.pr.view({ json: ['isDraft', 'number'] }),
    name: 'pr view',
    stdout: '{"isDraft":false,"number":7,"state":42}',
  },
  {
    argv: ['pr', 'list', '--head', 'feat-x', '--state', 'all', '--json', 'state'],
    expected: [{ state: 'OPEN' }],
    invalid: '[{}]',
    invoke: $ => $.gh.pr.list({ head: 'feat-x', json: ['state'], state: 'all' }),
    name: 'pr list',
    stdout: '[{"state":"OPEN","number":"ignored"}]',
  },
  {
    argv: ['release', 'list', '--json', 'tagName'],
    expected: [{ tagName: 'v1.0.0' }],
    invalid: '[{"tagName":42}]',
    invoke: $ => $.gh.release.list({ json: ['tagName'] }),
    name: 'release list',
    stdout: '[{"tagName":"v1.0.0"}]',
  },
  {
    argv: ['repo', 'view', '--json', 'nameWithOwner'],
    expected: { nameWithOwner: 'org/repo' },
    invalid: '{"nameWithOwner":null}',
    invoke: $ => $.gh.repo.view({ json: ['nameWithOwner'] }),
    name: 'repo view',
    stdout: '{"nameWithOwner":"org/repo"}',
  },
  {
    argv: [
      'run',
      'list',
      '--branch',
      'v1',
      '--event',
      'release',
      '--workflow',
      'release.yml',
      '--json',
      'databaseId,headBranch',
    ],
    expected: [{ databaseId: RUN_ID, headBranch: 'v1' }],
    invalid: '[{"databaseId":"123","headBranch":"v1"}]',
    invoke: $ =>
      $.gh.run.list({ branch: 'v1', event: 'release', json: ['databaseId', 'headBranch'], workflow: 'release.yml' }),
    name: 'run list',
    stdout: '[{"databaseId":123,"headBranch":"v1"}]',
  },
  {
    argv: ['api', 'repos/org/repo/pulls/123/reviews?per_page=100'],
    expected: [{ commit_id: 'sha', user: { login: 'copilot' } }],
    invalid: '[{"commit_id":"sha"}]',
    invoke: $ => $.gh.pr.reviews('org/repo', RUN_ID),
    name: 'pr reviews',
    stdout: '[{"commit_id":"sha","user":{"login":"copilot"}}]',
  },
];

describe('6.8 reading structured GitHub resources', () => {
  test('6.8.4 accepts a review from a deleted author', async ({ $, shell }) => {
    shell.otherwise('[{"commit_id":"deleted","user":null}]');
    const [review] = await $.gh.pr.reviews('org/repo', RUN_ID);
    expect(review?.user).toBeNull();
    expect(review?.commit_id).toBe('deleted');
  });

  test.for(jsonCases)(
    '6.8.1 validates and returns typed JSON for $name',
    async ({ argv, expected, invoke, stdout }, { $, shell }) => {
      shell.otherwise(stdout);
      expect(await invoke($)).toEqual(expected);
      expect(shell.calls[0]).toMatchObject({ argv, program: 'gh' });
    },
  );

  test.for(jsonCases)('6.8.2 rejects invalid fields for $name', async ({ invalid, invoke }, { $, shell }) => {
    shell.otherwise(invalid);
    await expect(invoke($)).rejects.toThrow();
  });

  test.for(jsonCases)('6.8.3 propagates command failures for $name', async ({ invoke }, { $, shell }) => {
    shell.otherwise({ exitCode: 1, stdout: 'unavailable' });
    await expect(invoke($)).rejects.toMatchObject({ exitCode: 1 });
  });
});

describe('6.9 checking an exact release tag', () => {
  test('6.9.1 finds an existing release by its exact tag', async ({ $, shell }) => {
    shell.otherwise('{"data":{"repository":{"release":{"id":"release-id"}}}}');
    const tag = 'old-tag/with"quotes';
    expect(await $.gh.release.exists(tag)).toBe(true);
    expect(shell.calls[0]?.argv).toContain(`tag=${tag}`);
    expect(shell.calls[0]?.argv).toContain(
      'query=query($owner: String!, $name: String!, $tag: String!) { repository(owner: $owner, name: $name) { release(tagName: $tag) { id } } }',
    );
  });

  test('6.9.2 returns false only when the release is absent', async ({ $, shell }) => {
    shell.otherwise('{"data":{"repository":{"release":null}}}');
    expect(await $.gh.release.exists('v1')).toBe(false);
  });

  test.for([
    '{}',
    '{"data":{"repository":null}}',
    '{"data":{"repository":{}}}',
    '{"data":{"repository":{"release":{}}}}',
  ])('6.9.3 rejects an invalid lookup response: %s', async (stdout, { $, shell }) => {
    shell.otherwise(stdout);
    await expect($.gh.release.exists('v1')).rejects.toThrow();
  });

  test('6.9.4 propagates lookup failures instead of reporting a missing release', async ({ $, shell }) => {
    shell.otherwise({ exitCode: 1, stdout: 'authentication failed' });
    await expect($.gh.release.exists('v1')).rejects.toMatchObject({ exitCode: 1 });
  });
});
