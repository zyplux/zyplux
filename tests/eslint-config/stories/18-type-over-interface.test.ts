import { describe, expect, test } from '#fixtures';

test.override({ ruleId: '@typescript-eslint/consistent-type-definitions', ruleName: 'type-over-interface' });

describe('18.1 rewriting interfaces into type aliases', () => {
  test('18.1.1 fixes a plain interface into an equivalent type alias, normalizing whitespace', ({
    fixRule,
    lintRule,
  }) => {
    expect(lintRule('interface User { id: string }')).toReport('typeOverInterface');
    expect(fixRule('interface User { id: string }')).toBe('type User = { id: string }');
    expect(fixRule('interface Squeezed{ id: string }')).toBe('type Squeezed = { id: string }');
    expect(fixRule('interface Stretched            { id: string }')).toBe('type Stretched = { id: string }');
  });

  test('18.1.2 fixes extends clauses into intersections and keeps type parameters', ({ fixRule }) => {
    expect(fixRule('type A = { a: string };\ninterface B extends A { b: string }')).toBe(
      'type A = { a: string };\ntype B = { b: string } & A',
    );
    expect(fixRule('interface Box<T> { value: T }')).toBe('type Box<T> = { value: T }');
    expect(fixRule('interface Pair extends Left, Right { id: string }')).toBe(
      'type Pair = { id: string } & Left & Right',
    );
    expect(fixRule('interface Wrap extends Box<T1>, Cache<T2> { id: string }')).toBe(
      'type Wrap = { id: string } & Box<T1> & Cache<T2>',
    );
  });

  test('18.1.3 fixes a default-exported interface into a named type alias with a default export', ({ fixRule }) => {
    expect(fixRule('export default interface Props { id: string }')).toBe(
      'type Props = { id: string }\nexport default Props',
    );
  });

  test('18.1.4 leaves a type alias alone, never preferring interfaces', ({ lintRule }) => {
    expect(lintRule('type User = { id: string };')).toReportNothing();
    expect(lintRule('type Pair = { id: string } & Left & Right;')).toReportNothing();
  });

  test('18.1.5 fixes an interface behind export and declare modifiers, keeping them in place', ({ fixRule }) => {
    expect(fixRule('export declare interface Env { region: string }')).toBe(
      'export declare type Env = { region: string }',
    );
  });
});

describe('18.2 exempting declaration-merging interfaces', () => {
  test('18.2.1 allows interfaces inside declare module and declare global blocks', ({ lintRule }) => {
    const moduleAugmentation = [
      "declare module 'vitest' {",
      '  interface Matchers<T> {',
      '    toBeFlagged: () => T;',
      '  }',
      '}',
      'export {};',
    ].join('\n');
    expect(lintRule(moduleAugmentation)).toReportNothing();
    const globalAugmentation = [
      'declare global {',
      '  interface Window {',
      '    appVersion: string;',
      '  }',
      '}',
      'export {};',
    ].join('\n');
    expect(lintRule(globalAugmentation)).toReportNothing();
  });

  test('18.2.2 flags and fixes an interface inside a plain namespace, which does not merge upstream', ({
    fixRule,
    lintRule,
  }) => {
    expect(lintRule('namespace Config { interface Options { id: string } }')).toReport('typeOverInterface');
    expect(fixRule('namespace Config { interface Options { id: string } }')).toBe(
      'namespace Config { type Options = { id: string } }',
    );
  });

  test('18.2.3 allows interfaces inside a declare namespace, whose ambient declarations merge', ({ lintRule }) => {
    expect(lintRule('declare namespace Stats { interface Entry { id: string } }')).toReportNothing();
  });

  test('18.2.4 allows an interface nested in a namespace inside declare global', ({ lintRule }) => {
    const nestedAugmentation = [
      'declare global {',
      '  namespace Stats {',
      '    interface Entry {',
      '      id: string;',
      '    }',
      '  }',
      '}',
      'export {};',
    ].join('\n');
    expect(lintRule(nestedAugmentation)).toReportNothing();
  });

  test('18.2.5 flags and fixes an interface inside a global block that lacks the declare keyword', ({
    fixRule,
    lintRule,
  }) => {
    expect(lintRule('global { interface Flags { id: string } }')).toReport('typeOverInterface');
    expect(fixRule('global { interface Flags { id: string } }')).toBe('global { type Flags = { id: string } }');
  });
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
