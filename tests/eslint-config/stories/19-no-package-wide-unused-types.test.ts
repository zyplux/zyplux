import { describe, test } from '#fixtures';

type PackageCase = [desc: string, packageSource: Record<string, string>, outcome: Record<string, string | undefined>];

const unusedCases: PackageCase[] = [
  [
    '1 flags a type only ever re-exported through a barrel',
    {
      'barrel.ts': "export type { Unused } from './unused-type';\n",
      'unused-type.ts': 'export type Unused = { readonly value: string };\n',
    },
    { 'barrel.ts': undefined, 'unused-type.ts': 'unusedExportedType' },
  ],
  [
    '2 flags a type only ever re-exported through a chain of barrels',
    {
      'barrel.ts': "export type { Chained } from './mid';\n",
      'chained-type.ts': 'export type Chained = { readonly value: string };\n',
      'mid.ts': "export type { Chained } from './chained-type';\n",
    },
    { 'barrel.ts': undefined, 'chained-type.ts': 'unusedExportedType', 'mid.ts': undefined },
  ],
  [
    '3 flags a declared but never-exported type',
    { 'local.ts': 'type Local = { readonly value: string };\nexport const noop = (): void => {};\n' },
    { 'local.ts': 'unusedLocalType' },
  ],
];

describe('19.1 flagging a type nothing else in the package uses', () => {
  test.for(unusedCases)('19.1.%s', ([, packageSource, outcome], { expectPackageOutcome, lintPackage }) => {
    expectPackageOutcome(lintPackage(packageSource), outcome);
  });
});

const usedCases: PackageCase[] = [
  [
    '1 allows a type referenced in a type position by another file',
    {
      'consumer.ts': [
        "import type { Used } from './used-type';",
        '',
        'export const readValue = (input: Used): string => input.value;',
        '',
      ].join('\n'),
      'used-type.ts': 'export type Used = { readonly value: string };\n',
    },
    { 'consumer.ts': undefined, 'used-type.ts': undefined },
  ],
  [
    "2 allows a type referenced only inside another type's definition",
    {
      'inner-type.ts': 'export type Inner = { readonly value: string };\n',
      'outer-type.ts': "import type { Inner } from './inner-type';\nexport type Outer = { readonly inner: Inner };\n",
    },
    { 'inner-type.ts': undefined, 'outer-type.ts': 'unusedExportedType' },
  ],
];

describe('19.2 allowing a type used anywhere in the package', () => {
  test.for(usedCases)('19.2.%s', ([, packageSource, outcome], { expectPackageOutcome, lintPackage }) => {
    expectPackageOutcome(lintPackage(packageSource), outcome);
  });
});
