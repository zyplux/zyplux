import { libraryTest } from '@zyplux/spectra';
import { mapWithConcurrency } from '@zyplux/util';

export const test = libraryTest.extend('mapWithConcurrency', () => mapWithConcurrency);

export { describe, expect } from 'vitest';
