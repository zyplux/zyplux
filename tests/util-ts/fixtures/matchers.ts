import { registerMatchers } from '@zyplux/tests-fixtures';
import { isDeepStrictEqual } from 'node:util';
import { ZodError } from 'zod';

export type TomlOutcome = 'schemaError' | 'syntaxError' | 'valid';

const describeThrown = (thrown: unknown) => (thrown instanceof Error ? thrown.message : String(thrown));

registerMatchers({
  toParseTomlAs: (parse: () => unknown, outcome: TomlOutcome, expectedValue?: unknown) => {
    let value: unknown;
    let thrown: unknown;
    try {
      value = parse();
    } catch (caught) {
      thrown = caught;
    }

    const isPass =
      outcome === 'valid'
        ? thrown === undefined && isDeepStrictEqual(value, expectedValue)
        : outcome === 'schemaError'
          ? thrown instanceof ZodError
          : thrown !== undefined;

    return {
      message: () =>
        outcome === 'valid'
          ? `expected parseToml to return ${JSON.stringify(expectedValue)}, got ${thrown ? `a throw (${describeThrown(thrown)})` : JSON.stringify(value)}`
          : `expected parseToml to throw a ${outcome}, but ${thrown ? `it threw ${describeThrown(thrown)}` : `it returned ${JSON.stringify(value)}`}`,
      pass: isPass,
    };
  },
});

declare module 'vitest' {
  interface Matchers<T> {
    toParseTomlAs: (outcome: TomlOutcome, expectedValue?: unknown) => T;
  }
}
