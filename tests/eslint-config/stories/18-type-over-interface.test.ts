import { describe, expect, test } from '#fixtures';

test.override({ ruleId: '@typescript-eslint/consistent-type-definitions', ruleName: 'type-over-interface' });

type FixCase = [shape: string, code: string, fixed: string, reportId?: string];
type FixFixtures = { fixRule: (code: string) => string; lintRule: (code: string) => unknown };
type LintFixtures = { lintRule: (code: string) => unknown };
type ReportNothingCase = [shape: string, code: string];

const runFixCase = ([, code, fixed, reportId]: FixCase, { fixRule, lintRule }: FixFixtures) => {
  if (reportId !== undefined) expect(lintRule(code)).toReport(reportId);
  expect(fixRule(code)).toBe(fixed);
};

const runReportNothingCase = ([, code]: ReportNothingCase, { lintRule }: LintFixtures) => {
  expect(lintRule(code)).toReportNothing();
};

describe('18.1 rewriting interfaces into type aliases', () => {
  const fixCases: FixCase[] = [
    [
      '1 fixes a plain interface into an equivalent type alias',
      'interface User { id: string }',
      'type User = { id: string }',
      'typeOverInterface',
    ],
    [
      '2 normalizes squeezed whitespace before the brace',
      'interface Squeezed{ id: string }',
      'type Squeezed = { id: string }',
    ],
    [
      '3 normalizes stretched whitespace before the brace',
      'interface Stretched            { id: string }',
      'type Stretched = { id: string }',
    ],
    [
      '4 fixes an extends clause into an intersection',
      'type A = { a: string };\ninterface B extends A { b: string }',
      'type A = { a: string };\ntype B = { b: string } & A',
    ],
    ['5 keeps a type parameter on the fixed alias', 'interface Box<T> { value: T }', 'type Box<T> = { value: T }'],
    [
      '6 fixes multiple extends clauses into an intersection',
      'interface Pair extends Left, Right { id: string }',
      'type Pair = { id: string } & Left & Right',
    ],
    [
      '7 keeps type arguments on extended intersection members',
      'interface Wrap extends Box<T1>, Cache<T2> { id: string }',
      'type Wrap = { id: string } & Box<T1> & Cache<T2>',
    ],
    [
      '8 fixes a default-exported interface into a named type alias with a default export',
      'export default interface Props { id: string }',
      'type Props = { id: string }\nexport default Props',
    ],
    [
      '9 fixes an interface behind export and declare modifiers, keeping them in place',
      'export declare interface Env { region: string }',
      'export declare type Env = { region: string }',
    ],
  ];

  test.for(fixCases)('18.1.%s', runFixCase);

  test.for<ReportNothingCase>([
    ['10 leaves a plain type alias alone', 'type User = { id: string };'],
    ['11 leaves a type alias with an intersection alone', 'type Pair = { id: string } & Left & Right;'],
  ])('18.1.%s', runReportNothingCase);
});

describe('18.2 exempting declaration-merging interfaces', () => {
  const fixCases: FixCase[] = [
    [
      '1 flags and fixes an interface inside a plain namespace, which does not merge upstream',
      'namespace Config { interface Options { id: string } }',
      'namespace Config { type Options = { id: string } }',
      'typeOverInterface',
    ],
    [
      '2 flags and fixes an interface inside a global block that lacks the declare keyword',
      'global { interface Flags { id: string } }',
      'global { type Flags = { id: string } }',
      'typeOverInterface',
    ],
  ];

  test.for(fixCases)('18.2.%s', runFixCase);

  test.for<ReportNothingCase>([
    [
      '3 allows an interface inside a declare module block',
      [
        "declare module 'vitest' {",
        '  interface Matchers<T> {',
        '    toBeFlagged: () => T;',
        '  }',
        '}',
        'export {};',
      ].join('\n'),
    ],
    [
      '4 allows an interface inside a declare global block',
      ['declare global {', '  interface Window {', '    appVersion: string;', '  }', '}', 'export {};'].join('\n'),
    ],
    [
      '5 allows interfaces inside a declare namespace, whose ambient declarations merge',
      'declare namespace Stats { interface Entry { id: string } }',
    ],
    [
      '6 allows an interface nested in a namespace inside declare global',
      [
        'declare global {',
        '  namespace Stats {',
        '    interface Entry {',
        '      id: string;',
        '    }',
        '  }',
        '}',
        'export {};',
      ].join('\n'),
    ],
  ])('18.2.%s', runReportNothingCase);
});

describe('18.3 replacing the upstream preference in the shipped config', () => {
  test('18.3.1 enables the rule for every typescript file', ({ zyplux }) => {
    const config = zyplux();
    const entries = config.filter(entry => entry.rules?.['@zyplux/type-over-interface'] !== undefined);
    expect(entries.map(entry => entry.files)).toEqual([['**/*.{ts,tsx}']]);
  });

  test('18.3.2 resolves the upstream consistent-type-definitions rule to off', ({ lint }) => {
    expect(lint('interface Foo { a: string }')).toReportNothing();
  });
});
