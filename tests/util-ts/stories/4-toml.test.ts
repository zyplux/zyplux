import { describe, expect, test } from '#fixtures';

const validToml = ['[project]', 'name = "cerberus"', 'dependencies = ["httpx>=0.28"]'].join('\n');
const validValue = { project: { dependencies: ['httpx>=0.28'], name: 'cerberus' } };

const malformedToml = 'name = ';
const schemaMismatchToml = '[project]\nname = 123';

type SchemaCase = [shape: string, text: string, expectedFailure?: 'schema' | 'syntax'];

const schemaCases: SchemaCase[] = [
  ['4.1.1 returns the schema validated value for well formed toml', validToml],
  ['4.1.2 throws on malformed toml syntax', malformedToml, 'syntax'],
  ['4.1.3 throws a zod error when the parsed value does not match the schema', schemaMismatchToml, 'schema'],
];

describe('4. Parsing TOML into schema-validated values', () => {
  describe('4.1 parsing toml text against a schema', () => {
    test.for(schemaCases)('%s', ([, text, expectedFailure], { parseToml, pyProjectSchema, zodError }) => {
      if (expectedFailure === undefined) {
        expect(parseToml(text, pyProjectSchema)).toEqual(validValue);
      } else if (expectedFailure === 'syntax') {
        expect(() => parseToml(text, pyProjectSchema)).toThrow();
      } else {
        expect(() => parseToml(text, pyProjectSchema)).toThrow(zodError);
      }
    });
  });

  type TryParseCase = [shape: string, text: string, expected: typeof validValue | undefined];

  const tryParseCases: TryParseCase[] = [
    ['4.2.1 returns the schema validated value for well formed toml', validToml, validValue],
    ['4.2.2 returns undefined instead of throwing on malformed toml syntax', malformedToml, undefined],
    [
      '4.2.3 returns undefined instead of throwing when the parsed value does not match the schema',
      schemaMismatchToml,
      undefined,
    ],
  ];

  describe('4.2 parsing toml text without throwing', () => {
    test.for(tryParseCases)('%s', ([, text, expected], { pyProjectSchema, tryParseToml }) => {
      expect(tryParseToml(text, pyProjectSchema)).toEqual(expected);
    });
  });
});
