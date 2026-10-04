import { libraryTest } from '@zyplux/spectra';
import { $, readTrimmed } from '@zyplux/util';

import { assertGhTypes } from './gh-types.ts';
export type Shell = typeof $;
export type { ShellFake } from '@zyplux/spectra';

export const test = libraryTest
  .extend('$', () => $)
  .extend('readTrimmed', () => readTrimmed)
  .extend('assertGhTypes', () => assertGhTypes);

export { describe, expect } from 'vitest';
