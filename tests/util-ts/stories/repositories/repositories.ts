import { libraryTest } from '@zyplux/spectra';
import { normalizeRepoUrl } from '@zyplux/util';

export const test = libraryTest.extend('normalizeRepoUrl', () => normalizeRepoUrl);

export { describe, expect } from 'vitest';
