import { libraryTest } from '@zyplux/spectra/library-test-api';
import { normalizeRepoUrl } from '@zyplux/util/repo-url';

export const test = libraryTest.extend('normalizeRepoUrl', () => normalizeRepoUrl);

export { describe, expect } from 'vitest';
