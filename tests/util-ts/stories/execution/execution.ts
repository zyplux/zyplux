import { libraryTest } from '@zyplux/spectra';
import { run } from '@zyplux/util/exec';

export const test = libraryTest.extend('run', () => run);

export { describe, expect } from 'vitest';
