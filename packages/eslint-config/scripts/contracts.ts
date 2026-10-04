import * as z from 'zod';

export const PrintedConfigSchema = z.looseObject({
  languageOptions: z.looseObject({ parserOptions: z.looseObject({ tsconfigRootDir: z.string() }) }),
});
