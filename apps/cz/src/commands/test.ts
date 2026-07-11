import { captureMerged, ensure } from '@zyplux/util';
import { existsSync } from 'node:fs';

import type { InferValue } from '#optique';

import { argument, command, constant, merge, message, object, optional, string } from '#optique';

const PYTEST_NO_TESTS_COLLECTED = 5;

type Runner = {
  argv: (name: string | undefined) => Promise<string[]> | string[];
  label: string;
  manifest: string;
  toleratedExitCode?: number;
};

const resolveJsFilters = async (name: string) => {
  const { createVitest } = await import('vitest/node');
  const vitest = await createVitest('test', { passWithNoTests: true, watch: false });
  try {
    const { testModules } = await vitest.collect(undefined, { staticParse: true });
    const pattern = new RegExp(name);
    const matches = testModules
      .map(testModule => ({
        moduleId: testModule.moduleId,
        nameMatch: testModule.children.allTests().some(testCase => pattern.test(testCase.fullName)),
        pathMatch: pattern.test(testModule.moduleId),
      }))
      .filter(match => match.pathMatch || match.nameMatch);
    return {
      moduleIds: matches.map(match => match.moduleId),
      scopeToName: matches.length > 0 && matches.every(match => !match.pathMatch),
    };
  } finally {
    await vitest.close();
  }
};

const PYTEST_KEYWORD_RESERVED_WORDS = new Set(['and', 'not', 'or']);

const toPytestKeywordExpr = (name: string) =>
  name
    .split(/\s+/)
    .map(word => word.replaceAll(/[^\w:+.[\]\\/-]/g, ''))
    .filter(word => word.length > 0 && !PYTEST_KEYWORD_RESERVED_WORDS.has(word))
    .join(' and ');

const RUNNERS: Runner[] = [
  {
    argv: async name => {
      if (name === undefined) return ['bun', 'run', 'test'];
      const { moduleIds, scopeToName } = await resolveJsFilters(name);
      if (moduleIds.length === 0) return [];
      const selectors = scopeToName ? [...moduleIds, '-t', name] : moduleIds;
      return [
        'bun',
        'run',
        'test',
        ...selectors,
        '--passWithNoTests',
        '--coverage.enabled=false',
        '--reporter=tree',
        '--hideSkippedTests',
      ];
    },
    label: 'JS',
    manifest: 'package.json',
  },
  {
    argv: name => [
      'uv',
      'run',
      'pytest',
      ...(name === undefined ? [] : ['--no-cov', '-v', '-k', toPytestKeywordExpr(name)]),
    ],
    label: 'Python',
    manifest: 'pyproject.toml',
    toleratedExitCode: PYTEST_NO_TESTS_COLLECTED,
  },
];

const nameArgument = argument(string({ metavar: 'NAME' }), {
  description: message`Run only tests matching this name; skips coverage and passes when nothing matches.`,
});

const testParser = merge(object({ command: constant('test' as const) }), object({ name: optional(nameArgument) }));

export const testCommand = command('test', testParser, {
  brief: message`Run JS (bun run test) and Python (uv run pytest) workspace tests in parallel, printing each buffered log once both finish.`,
});

type TestConfig = InferValue<typeof testCommand>;

export const runTest = async ({ name }: TestConfig) => {
  const runners = RUNNERS.filter(runner => existsSync(runner.manifest));
  ensure(runners.length > 0, `no test workspace found: neither package.json nor pyproject.toml is in ${process.cwd()}`);

  const results = await Promise.all(
    runners.map(async runner => {
      const argv = await runner.argv(name);
      const output = argv.length === 0 ? { exitCode: 0, text: () => '' } : await captureMerged(argv);
      return { output, runner };
    }),
  );

  const failedLabels: string[] = [];
  for (const { output, runner } of results) {
    const log = output.text().trimEnd();
    if (log.length > 0) console.log(log);
    if (output.exitCode !== 0 && output.exitCode !== runner.toleratedExitCode) failedLabels.push(runner.label);
  }
  ensure(failedLabels.length === 0, `tests failed: ${failedLabels.join(', ')}`);
};
