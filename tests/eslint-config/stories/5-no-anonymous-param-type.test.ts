import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-anonymous-param-type' });

describe('5.1 flagging inline object types in parameter position', () => {
  test('5.1.1 flags a top-level inline object type on plain and destructured parameters', ({ lintRule }) => {
    expect(lintRule('const f = (x: { a: string }) => x.a;')).toReport('nameParameterType');
    expect(lintRule('const f = ({ a }: { a: string }) => a;')).toReport('nameParameterType');
  });

  test('5.1.2 flags function declaration and object method parameters', ({ lintRule }) => {
    expect(lintRule('function read(opts: { id: number }) { return opts.id; }')).toReport('nameParameterType');
    expect(lintRule('const o = { read(p: { x: string }) { return p.x; } };')).toReport('nameParameterType');
  });

  test('5.1.3 reports each parameter with an inline object type', ({ lintRule }) => {
    expect(lintRule('const f = (a: { x: string }, b: { y: number }) => a.x;')).toReport(
      'nameParameterType',
      'nameParameterType',
    );
  });

  test('5.1.4 flags an object literal as a union or intersection member', ({ lintRule }) => {
    expect(lintRule('const f = (x: { a: string } | undefined) => x?.a;')).toReport('nameParameterType');
    expect(lintRule('const f = (x: Base & { a: string }) => x.a;')).toReport('nameParameterType');
  });

  test('5.1.5 reports every object literal in a union separately', ({ lintRule }) => {
    expect(lintRule('const f = (x: { a: string } | { b: number }) => x;')).toReport(
      'nameParameterType',
      'nameParameterType',
    );
  });

  test('5.1.6 flags a parameter with a default value', ({ lintRule }) => {
    expect(lintRule('const f = (x: { a: string } = { a: "" }) => x.a;')).toReport('nameParameterType');
  });

  test('5.1.7 flags a constructor parameter property', ({ lintRule }) => {
    expect(lintRule('class C { constructor(public opts: { a: string }) {} }')).toReport('nameParameterType');
  });
});

describe('5.2 permitting named, primitive, and non-parameter object types', () => {
  test('5.2.1 allows a named type reference, a primitive, and an untyped parameter', ({ lintRule }) => {
    expect(lintRule('const f = (x: Foo) => x;')).toReportNothing();
    expect(lintRule('const f = (x: string) => x;')).toReportNothing();
    expect(lintRule('const f = x => x;')).toReportNothing();
  });

  test('5.2.2 allows inline object types outside parameter position', ({ lintRule }) => {
    expect(lintRule('const f = (x: string): { a: string } => ({ a: x });')).toReportNothing();
    expect(lintRule('const x: { a: string } = { a: "" };')).toReportNothing();
    expect(lintRule('type T = { a: string };')).toReportNothing();
  });

  test('5.2.3 allows an object literal that describes a container element, not the parameter', ({ lintRule }) => {
    expect(lintRule('const f = (rows: { id: string }[]) => rows.length;')).toReportNothing();
    expect(lintRule('const f = (x: Array<{ a: string }>) => x.length;')).toReportNothing();
    expect(lintRule('const f = (x: Record<string, { a: number }>) => x;')).toReportNothing();
  });
});
