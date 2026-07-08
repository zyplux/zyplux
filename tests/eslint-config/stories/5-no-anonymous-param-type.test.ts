import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-anonymous-param-type' });

const oneReport = [{ messageId: 'nameParameterType' }];
const twoReports = [{ messageId: 'nameParameterType' }, { messageId: 'nameParameterType' }];

describe('5.1 flagging inline object types in parameter position', () => {
  test('5.1.1 flags a top-level inline object type on plain and destructured parameters', ({ lintRule }) => {
    expect(lintRule('const f = (x: { a: string }) => x.a;')).toMatchObject(oneReport);
    expect(lintRule('const f = ({ a }: { a: string }) => a;')).toMatchObject(oneReport);
  });

  test('5.1.2 flags function declaration and object method parameters', ({ lintRule }) => {
    expect(lintRule('function read(opts: { id: number }) { return opts.id; }')).toMatchObject(oneReport);
    expect(lintRule('const o = { read(p: { x: string }) { return p.x; } };')).toMatchObject(oneReport);
  });

  test('5.1.3 reports each parameter with an inline object type', ({ lintRule }) => {
    expect(lintRule('const f = (a: { x: string }, b: { y: number }) => a.x;')).toMatchObject(twoReports);
  });

  test('5.1.4 flags an object literal as a union or intersection member', ({ lintRule }) => {
    expect(lintRule('const f = (x: { a: string } | undefined) => x?.a;')).toMatchObject(oneReport);
    expect(lintRule('const f = (x: Base & { a: string }) => x.a;')).toMatchObject(oneReport);
  });

  test('5.1.5 reports every object literal in a union separately', ({ lintRule }) => {
    expect(lintRule('const f = (x: { a: string } | { b: number }) => x;')).toMatchObject(twoReports);
  });

  test('5.1.6 flags a parameter with a default value', ({ lintRule }) => {
    expect(lintRule('const f = (x: { a: string } = { a: "" }) => x.a;')).toMatchObject(oneReport);
  });

  test('5.1.7 flags a constructor parameter property', ({ lintRule }) => {
    expect(lintRule('class C { constructor(public opts: { a: string }) {} }')).toMatchObject(oneReport);
  });
});

describe('5.2 permitting named, primitive, and non-parameter object types', () => {
  test('5.2.1 allows a named type reference, a primitive, and an untyped parameter', ({ lintRule }) => {
    expect(lintRule('const f = (x: Foo) => x;')).toHaveLength(0);
    expect(lintRule('const f = (x: string) => x;')).toHaveLength(0);
    expect(lintRule('const f = x => x;')).toHaveLength(0);
  });

  test('5.2.2 allows inline object types outside parameter position', ({ lintRule }) => {
    expect(lintRule('const f = (x: string): { a: string } => ({ a: x });')).toHaveLength(0);
    expect(lintRule('const x: { a: string } = { a: "" };')).toHaveLength(0);
    expect(lintRule('type T = { a: string };')).toHaveLength(0);
  });

  test('5.2.3 allows an object literal that describes a container element, not the parameter', ({ lintRule }) => {
    expect(lintRule('const f = (rows: { id: string }[]) => rows.length;')).toHaveLength(0);
    expect(lintRule('const f = (x: Array<{ a: string }>) => x.length;')).toHaveLength(0);
    expect(lintRule('const f = (x: Record<string, { a: number }>) => x;')).toHaveLength(0);
  });
});
