import { describe, expect, test, type TomlOutcome } from '#fixtures';

const validToml = ['[project]', 'name = "cerberus"', 'dependencies = ["httpx>=0.28"]'].join('\n');
const validValue = { project: { dependencies: ['httpx>=0.28'], name: 'cerberus' } };

const malformedToml = 'name = ';
const schemaMismatchToml = '[project]\nname = 123';

type TomlCase = [shape: string, text: string, outcome: TomlOutcome];

const tomlCases: TomlCase[] = [
  ['1 well formed toml matching the schema', validToml, 'valid'],
  ['2 malformed toml syntax', malformedToml, 'syntaxError'],
  ['3 toml that does not match the schema', schemaMismatchToml, 'schemaError'],
];

describe('4. Parsing TOML into schema-validated values', () => {
  describe('4.1 parsing toml text against a schema', () => {
    test.for(tomlCases)('4.1.%s', ([, text, outcome], { parseToml, pyProjectSchema }) => {
      expect(() => parseToml(text, pyProjectSchema)).toParseTomlAs(outcome, validValue);
    });
  });

  describe('4.2 parsing toml text without throwing', () => {
    test.for(tomlCases)('4.2.%s', ([, text, outcome], { pyProjectSchema, tryParseToml }) => {
      expect(tryParseToml(text, pyProjectSchema)).toEqual(outcome === 'valid' ? validValue : undefined);
    });
  });
});
