import { libraryTest } from '@zyplux/spectra/library-test-api';
import { mapWithConcurrency } from '@zyplux/util/map-with-concurrency';

export const test = libraryTest.extend('mapWithConcurrency', () => mapWithConcurrency);

export { describe, expect } from 'vitest';
