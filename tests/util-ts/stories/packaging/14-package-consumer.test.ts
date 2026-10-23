import { describe, test } from './packaging.ts';

describe('14.1 consuming published packages', () => {
  test(
    '14.1.2 supports util imports with an optional TypeScript peer',
    { timeout: 90_000 },
    async ({ verifyUtilPackage }) => {
      await verifyUtilPackage();
    },
  );
});
