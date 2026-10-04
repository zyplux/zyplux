import { describe, expect, test } from './architecture.ts';

describe('24.1 resolving suite APIs', () => {
  test.for([
    ['1 accepts an extensionless UI API', 'import { test } from "../rigs";', []],
    ['2 accepts a configured TypeScript alias', 'import { test, type Fixture } from "#api";', []],
    ['3 rejects a helper renamed to test', 'import { helper as test } from "#api";', ['bindingOutsideSeam']],
    ['4 rejects value re-exports from the API', 'export { test } from "#api";', ['bindingOutsideSeam']],
    ['5 rejects direct Vitest dynamic imports', 'const load = () => import("vitest");', ['moduleOutsideSeam']],
  ] as const)('24.1.%s', async ([, source, expected], { lintArchitecture }) => {
    const filename = 'apps/widget/tests/stories/ui.test.ts';
    const reports = await lintArchitecture(
      {
        'apps/widget/tests/rigs.ts':
          'export const test = () => {}; export const helper = () => {}; export type Fixture = string;',
        [filename]: source,
        'tsconfig.json': '{"compilerOptions":{"paths":{"#api":["./apps/widget/tests/rigs.ts"]}},"include":["**/*.ts"]}',
      },
      'test-seam-only-imports',
      [{ testApi: 'apps/widget/tests/rigs.ts' }],
      filename,
    );
    expect(reports.map(report => report.messageId)).toEqual(expected);
  });
});
