import type { UserConsoleLog } from 'vitest';
import type { Reporter, SerializedError, TestModule, TestRunEndReason, Vitest } from 'vitest/node';

import { existsSync } from 'node:fs';
import path from 'node:path';

const INFO_PREFIX = '<6>';
const WARNING_PREFIX = '<4>';
const ERROR_PREFIX = '<3>';

import { openJournalWriter } from './journal-writer.ts';

type JournaldReporterOptions = { identifier?: string; isEnabled?: boolean; socketPath?: string };

type JournalWriter = ReturnType<typeof openJournalWriter>;

const formatErrors = (errors: readonly SerializedError[]) =>
  errors.flatMap(error => {
    const stack = error.stack ?? '';
    const message = error.message;
    const text = stack.includes(message) ? stack : `${message}\n${stack}`;
    return text
      .trimEnd()
      .split('\n')
      .map(line => `${ERROR_PREFIX}  ${line}`);
  });

const formatFailures = (module: TestModule) => {
  const modulePath = path.relative(process.cwd(), module.moduleId);
  return [
    ...[module, ...module.children.allSuites()].flatMap(suite =>
      suite.errors().length === 0
        ? []
        : [
            `${ERROR_PREFIX}FAIL ${modulePath}${suite.type === 'module' ? '' : ` > ${suite.fullName}`}`,
            ...formatErrors(suite.errors()),
          ],
    ),
    ...[...module.children.allTests('failed')].flatMap(test => [
      `${ERROR_PREFIX}FAIL ${modulePath} > ${test.fullName}`,
      ...formatErrors(test.result().errors ?? []),
    ]),
  ];
};

export class JournaldReporter implements Reporter {
  #context: undefined | Vitest;
  readonly #identifier: string;
  readonly #isEnabled: boolean;
  readonly #socketPath: string;
  #startedAt = '';
  readonly #writers = new Map<string, JournalWriter>();

  constructor({
    identifier = 'spectra',
    socketPath = '/run/systemd/journal/stdout',
    isEnabled = existsSync(socketPath),
  }: JournaldReporterOptions = {}) {
    this.#identifier = identifier;
    this.#isEnabled = isEnabled;
    this.#socketPath = socketPath;
  }

  onInit(context: Vitest) {
    this.#context = context;
  }

  async onTestRunEnd(modules: readonly TestModule[], errors: readonly SerializedError[], reason: TestRunEndReason) {
    const projects = Map.groupBy(modules, module => module.project.name);
    for (const [project, projectModules] of projects) {
      const tests = projectModules.flatMap(module => [...module.children.allTests()]);
      const passed = tests.filter(test => test.result().state === 'passed').length;
      const failed = tests.filter(test => test.result().state === 'failed').length;
      const pending = tests.length - passed - failed;
      const hasFailed = projectModules.some(module => !module.ok()) || errors.length > 0 || reason === 'interrupted';
      this.#write(project ? `${this.#identifier}-${project}` : this.#identifier, [
        `${INFO_PREFIX}run start ${this.#startedAt}`,
        ...projectModules.flatMap(module => formatFailures(module)),
        `${hasFailed ? ERROR_PREFIX : INFO_PREFIX}${hasFailed ? 'FAIL' : 'pass'} — ${tests.length} tests: ${passed} passed, ${failed} failed, ${pending} pending`,
      ]);
    }
    if (errors.length > 0) this.#write(this.#identifier, formatErrors(errors));
    for (const writer of this.#writers.values()) await writer.close();
    this.#writers.clear();
  }

  onTestRunStart() {
    this.#startedAt = new Date().toISOString();
  }

  onUserConsoleLog({ content, taskId, type }: UserConsoleLog) {
    const trimmed = content.trimEnd();
    if (!trimmed) return;
    const entity = taskId ? this.#context?.state.getReportedEntityById(taskId) : undefined;
    const module = entity?.type === 'module' ? entity : entity?.module;
    const identifier = module?.project.name ? `${this.#identifier}-${module.project.name}` : this.#identifier;
    const modulePath = module ? path.relative(process.cwd(), module.moduleId) : '<no test>';
    const source = entity && entity.type !== 'module' ? `${modulePath} > ${entity.fullName}` : modulePath;
    const prefix = type === 'stdout' ? INFO_PREFIX : WARNING_PREFIX;
    this.#write(
      `${identifier}-console`,
      trimmed.split('\n').map(line => `${prefix}${source} ${line}`),
    );
  }

  #write(identifier: string, lines: readonly string[]) {
    if (!this.#isEnabled) return;
    let writer = this.#writers.get(identifier);
    if (!writer) {
      writer = openJournalWriter(identifier, this.#socketPath);
      this.#writers.set(identifier, writer);
    }
    writer.write(lines);
  }
}
