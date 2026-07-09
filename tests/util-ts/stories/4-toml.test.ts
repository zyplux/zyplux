import * as z from 'zod';

import { describe, expect, test } from '#fixtures';

const ConfigSchema = z.object({
  features: z.array(z.string()).optional(),
  package: z.object({ name: z.string(), version: z.string() }),
});

const validToml = ['features = ["a", "b"]', '', '[package]', 'name = "cerberus"', 'version = "1.2.3"'].join('\n');
const validValue = { features: ['a', 'b'], package: { name: 'cerberus', version: '1.2.3' } };

const malformedToml = 'name = ';
const schemaMismatchToml = '[package]\nname = "cerberus"';

describe('parseToml', () => {
  describe('4.1 parsing toml text against a schema', () => {
    test('4.1.1 returns the schema validated value for well formed toml', ({ parseToml }) => {
      expect(parseToml(validToml, ConfigSchema)).toEqual(validValue);
    });

    test('4.1.2 throws on malformed toml syntax', ({ parseToml }) => {
      expect(() => parseToml(malformedToml, ConfigSchema)).toThrow();
    });

    test('4.1.3 throws a zod error when the parsed value does not match the schema', ({ parseToml }) => {
      expect(() => parseToml(schemaMismatchToml, ConfigSchema)).toThrow(z.ZodError);
    });
  });
});

describe('tryParseToml', () => {
  describe('4.2 parsing toml text without throwing', () => {
    test('4.2.1 returns the schema validated value for well formed toml', ({ tryParseToml }) => {
      expect(tryParseToml(validToml, ConfigSchema)).toEqual(validValue);
    });

    test('4.2.2 returns undefined instead of throwing on malformed toml syntax', ({ tryParseToml }) => {
      expect(tryParseToml(malformedToml, ConfigSchema)).toBeUndefined();
    });

    test('4.2.3 returns undefined instead of throwing when the parsed value does not match the schema', ({ tryParseToml }) => {
      expect(tryParseToml(schemaMismatchToml, ConfigSchema)).toBeUndefined();
    });
  });
});
