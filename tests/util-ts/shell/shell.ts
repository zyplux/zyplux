import { libraryTest } from '@zyplux/spectra/library-test-api';
import { $, readTrimmed } from '@zyplux/util/shell';

import { assertGhTypes } from './gh-types.ts';
export type Shell = typeof $;
export type { ShellFake } from '@zyplux/spectra/shell-fake';

export const test = libraryTest
  .extend('$', () => $)
  .extend('readTrimmed', () => readTrimmed)
  .extend('assertGhTypes', () => assertGhTypes);

export { describe, expect } from 'vitest';
