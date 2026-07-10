import { describe, expect, test } from '#fixtures';

const validToml = ['[project]', 'name = "cerberus"', 'dependencies = ["httpx>=0.28"]'].join('\n');
const validValue = { project: { dependencies: ['httpx>=0.28'], name: 'cerberus' } };

const malformedToml = 'name = ';
const schemaMismatchToml = '[project]\nname = 123';

describe('parseToml', () => {
  describe('4.1 parsing toml text against a schema', () => {
    test('4.1.1 returns the schema validated value for well formed toml', ({ parseToml, pyProjectSchema }) => {
      expect(parseToml(validToml, pyProjectSchema)).toEqual(validValue);
    });

    test('4.1.2 throws on malformed toml syntax', ({ parseToml, pyProjectSchema }) => {
      expect(() => parseToml(malformedToml, pyProjectSchema)).toThrow();
    });

    test('4.1.3 throws a zod error when the parsed value does not match the schema', ({
      parseToml,
      pyProjectSchema,
      zodError,
    }) => {
      expect(() => parseToml(schemaMismatchToml, pyProjectSchema)).toThrow(zodError);
    });
  });
});

describe('tryParseToml', () => {
  describe('4.2 parsing toml text without throwing', () => {
    test('4.2.1 returns the schema validated value for well formed toml', ({ pyProjectSchema, tryParseToml }) => {
      expect(tryParseToml(validToml, pyProjectSchema)).toEqual(validValue);
    });

    test('4.2.2 returns undefined instead of throwing on malformed toml syntax', ({
      pyProjectSchema,
      tryParseToml,
    }) => {
      expect(tryParseToml(malformedToml, pyProjectSchema)).toBeUndefined();
    });

    test('4.2.3 returns undefined instead of throwing when the parsed value does not match the schema', ({
      pyProjectSchema,
      tryParseToml,
    }) => {
      expect(tryParseToml(schemaMismatchToml, pyProjectSchema)).toBeUndefined();
    });
  });
});
