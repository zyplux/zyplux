import { libraryTest } from '@zyplux/spectra/library-test-api';
import { PyProjectSchema } from '@zyplux/util/contracts';
import { parseToml, tryParseToml } from '@zyplux/util/toml';

import './toml-matchers.ts';
export type { TomlOutcome } from './toml-matchers.ts';

export const test = libraryTest
  .extend('parseToml', () => parseToml)
  .extend('tryParseToml', () => tryParseToml)
  .extend('pyProjectSchema', () => PyProjectSchema);

export { describe, expect } from 'vitest';
