import { parseToml, tryParseToml } from '@zyplux/util';
import { describe, expect, it } from 'vitest';
import * as z from 'zod';

const ConfigSchema = z.object({
  features: z.array(z.string()).optional(),
  package: z.object({ name: z.string(), version: z.string() }),
});

const valid = ['features = ["a", "b"]', '', '[package]', 'name = "cerberus"', 'version = "1.2.3"'].join('\n');

describe('parseToml', () => {
  it('parses a string and returns the schema-validated value', () => {
    expect(parseToml(valid, ConfigSchema)).toEqual({
      features: ['a', 'b'],
      package: { name: 'cerberus', version: '1.2.3' },
    });
  });

  it('throws on malformed TOML syntax', () => {
    expect(() => parseToml('name = ', ConfigSchema)).toThrow();
  });

  it('throws a ZodError when the shape does not match the schema', () => {
    expect(() => parseToml('[package]\nname = "cerberus"', ConfigSchema)).toThrow(z.ZodError);
  });
});

describe('tryParseToml', () => {
  it('returns the validated value on success', () => {
    expect(tryParseToml(valid, ConfigSchema)?.package.name).toBe('cerberus');
  });

  it('returns undefined on malformed TOML syntax', () => {
    expect(tryParseToml('name = ', ConfigSchema)).toBeUndefined();
  });

  it('returns undefined on a schema mismatch', () => {
    expect(tryParseToml('[package]\nname = "cerberus"', ConfigSchema)).toBeUndefined();
  });
});
