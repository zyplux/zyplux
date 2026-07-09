import type { Linter } from 'eslint';

export const applySuggestion = (code: string, { suggestions }: Linter.LintMessage, index = 0) => {
  const suggestion = suggestions?.[index];
  if (suggestion === undefined) throw new Error(`message has no suggestion at index ${index}`);
  const { range, text } = suggestion.fix;
  return code.slice(0, range[0]) + text + code.slice(range[1]);
};
