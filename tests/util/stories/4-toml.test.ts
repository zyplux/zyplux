import { parseToml, tryParseToml } from '@zyplux/util';
import { describe, expect, it } from 'vitest';
import * as z from 'zod';

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
    it('4.1.1 returns the schema validated value for well formed toml', () => {
      expect(parseToml(validToml, ConfigSchema)).toEqual(validValue);
    });

    it('4.1.2 throws on malformed toml syntax', () => {
      expect(() => parseToml(malformedToml, ConfigSchema)).toThrow();
    });

    it('4.1.3 throws a zod error when the parsed value does not match the schema', () => {
      expect(() => parseToml(schemaMismatchToml, ConfigSchema)).toThrow(z.ZodError);
    });
  });
});

describe('tryParseToml', () => {
  describe('4.2 parsing toml text without throwing', () => {
    it('4.2.1 returns the schema validated value for well formed toml', () => {
      expect(tryParseToml(validToml, ConfigSchema)).toEqual(validValue);
    });

    it('4.2.2 returns undefined instead of throwing on malformed toml syntax', () => {
      expect(tryParseToml(malformedToml, ConfigSchema)).toBeUndefined();
    });

    it('4.2.3 returns undefined instead of throwing when the parsed value does not match the schema', () => {
      expect(tryParseToml(schemaMismatchToml, ConfigSchema)).toBeUndefined();
    });
  });
});
