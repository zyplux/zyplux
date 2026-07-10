import type { Linter } from 'eslint';

import { registerMatchers } from '@zyplux/tests-fixtures';

export const applySuggestion = (code: string, { suggestions }: Linter.LintMessage, index = 0) => {
  const suggestion = suggestions?.[index];
  if (suggestion === undefined) throw new Error(`message has no suggestion at index ${index}`);
  const { range, text } = suggestion.fix;
  return code.slice(0, range[0]) + text + code.slice(range[1]);
};

const renderReports = (messages: Linter.LintMessage[]) =>
  messages.length === 0
    ? 'reported: (nothing)'
    : `reported:\n${messages.map(({ line, message, messageId }) => `  ${messageId ?? '(no messageId)'} at line ${line}: ${message}`).join('\n')}`;

export const lintMatchers = registerMatchers({
  toReport: (messages: Linter.LintMessage[], ...messageIds: [string, ...string[]]) => ({
    message: () => `asserted reports: [${messageIds.join(', ')}]\n${renderReports(messages)}`,
    pass:
      messages.length === messageIds.length &&
      messages.every(({ messageId }, index) => messageId === messageIds[index]),
  }),
  toReportNothing: (messages: Linter.LintMessage[]) => ({
    message: () => renderReports(messages),
    pass: messages.length === 0,
  }),
});

declare module 'vitest' {
  interface Matchers<T> {
    toReport: (...messageIds: [string, ...string[]]) => T;
    toReportNothing: () => T;
  }
}
