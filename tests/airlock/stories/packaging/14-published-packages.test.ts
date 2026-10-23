import { describe, test } from './packaging.ts';

describe('14.1 packing release targets', () => {
  test('14.1.1 passes Publint for every built npm archive', ({ verifyPublishedPackages }) => {
    verifyPublishedPackages();
  });
});
