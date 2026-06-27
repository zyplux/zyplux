import type { ZodType } from 'zod';

import { attempt } from './result';

export const parseToml = <T>(text: string, schema: ZodType<T>) => schema.parse(Bun.TOML.parse(text));

export const tryParseToml = <T>(text: string, schema: ZodType<T>): T | undefined => {
  const result = attempt(() => parseToml(text, schema));
  return result.ok ? result.data : undefined;
};
