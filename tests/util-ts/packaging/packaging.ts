import { libraryTest } from '@zyplux/spectra/library-test-api';

import { verifyUtilPackage } from './package-consumer.ts';

export const test = libraryTest.extend(
  'verifyUtilPackage',
  ({ tempDir }) =>
    () =>
      verifyUtilPackage(tempDir),
);
export { describe } from 'vitest';
