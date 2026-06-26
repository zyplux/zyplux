import type { ZodType } from 'zod';

import { readFileSync } from 'node:fs';

export const parseJson = <T>(text: string, schema: ZodType<T>) => schema.parse(JSON.parse(text));

export const readJson = async <T>(path: string | URL, schema: ZodType<T>) => schema.parse(await Bun.file(path).json());

export const readJsonSync = <T>(path: string | URL, schema: ZodType<T>) =>
  parseJson(readFileSync(path, 'utf8'), schema);
