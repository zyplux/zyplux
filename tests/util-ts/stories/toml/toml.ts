import { libraryTest } from '@zyplux/spectra';
import { parseToml, tryParseToml } from '@zyplux/util';
import { PyProjectSchema } from '@zyplux/util/contracts';

import './toml-matchers.ts';
export type { TomlOutcome } from './toml-matchers.ts';

export const test = libraryTest
  .extend('parseToml', () => parseToml)
  .extend('tryParseToml', () => tryParseToml)
  .extend('pyProjectSchema', () => PyProjectSchema);

export { describe, expect } from 'vitest';
