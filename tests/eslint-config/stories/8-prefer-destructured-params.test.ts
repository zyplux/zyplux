import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'prefer-destructured-params' });

describe('8.1 rewriting property-only parameters into destructuring patterns', () => {
  test('8.1.1 rewrites a single property read in a concise body', ({ fixRule, lintRule }) => {
    const code = 'const first = (node: Foo) => node.parent;';
    expect(lintRule(code)).toReport('destructureParameter');
    expect(fixRule(code)).toBe('const first = ({ parent }: Foo) => parent;');
  });

  test('8.1.2 turns several distinct properties into several bindings and a repeated read into one', ({ fixRule }) => {
    expect(fixRule('const sum = (node: Foo) => node.a + node.b;')).toBe('const sum = ({ a, b }: Foo) => a + b;');
    expect(fixRule('const twice = (node: Foo) => node.x + node.x;')).toBe('const twice = ({ x }: Foo) => x + x;');
  });

  test('8.1.3 rewrites function declaration and object method parameters', ({ fixRule }) => {
    expect(fixRule('function read(node: Foo) { return node.value; }')).toBe(
      'function read({ value }: Foo) { return value; }',
    );
    expect(fixRule('const obj = { read(node: Foo) { return node.value; } };')).toBe(
      'const obj = { read({ value }: Foo) { return value; } };',
    );
  });

  test('8.1.4 absorbs a const alias whose name already matches the property', ({ fixRule }) => {
    const code = [
      'const getName = (node: Foo) => {',
      '  const parent = node.parent;',
      '  return parent.id;',
      '};',
    ].join('\n');
    expect(fixRule(code)).toBe(['const getName = ({ parent }: Foo) => {', '  return parent.id;', '};'].join('\n'));
  });

  test('8.1.5 absorbs a const alias under a different name, renaming its references to the property', ({ fixRule }) => {
    const code = [
      'const check = (node: Foo) => {',
      '  const decl = node.parent;',
      '  return decl.type && decl.id;',
      '};',
    ].join('\n');
    expect(fixRule(code)).toBe(
      ['const check = ({ parent }: Foo) => {', '  return parent.type && parent.id;', '};'].join('\n'),
    );
  });

  test('8.1.6 combines an alias and a direct read into one pattern', ({ fixRule }) => {
    const code = ['const mix = (node: Foo) => {', '  const x = node.x;', '  return x + node.y;', '};'].join('\n');
    expect(fixRule(code)).toBe(['const mix = ({ x, y }: Foo) => {', '  return x + y;', '};'].join('\n'));
  });

  test('8.1.7 treats a non-const alias as a direct read, leaving the local binding in place', ({ fixRule }) => {
    expect(fixRule('const keep = (node: Foo) => { let x = node.y; return x; };')).toBe(
      'const keep = ({ y }: Foo) => { let x = y; return x; };',
    );
  });

  test('8.1.8 destructures only the property-only parameter, leaving a method-receiver parameter alone', ({
    fixRule,
  }) => {
    const code = [
      'const reExported = (node: Foo, set: Bar) => {',
      '  if (set.size === 0) return false;',
      '  const decl = node.parent;',
      '  return decl.type && set.has(decl.id);',
      '};',
    ].join('\n');
    expect(fixRule(code)).toBe(
      [
        'const reExported = ({ parent }: Foo, set: Bar) => {',
        '  if (set.size === 0) return false;',
        '  return parent.type && set.has(parent.id);',
        '};',
      ].join('\n'),
    );
  });
});

describe('8.2 reporting without an autofix when destructuring would collide', () => {
  test('8.2.1 reports a collision with a function-scoped local without offering an autofix', ({ lintRule }) => {
    const code = [
      'const collide = (node: Foo) => {',
      '  const parent = 1;',
      '  return node.parent + parent;',
      '};',
    ].join('\n');
    expect(lintRule(code)).toReport('destructureParameterNoFix');
  });

  test('8.2.2 reports a same-named local alias clash without offering an autofix', ({ lintRule }) => {
    expect(lintRule('const shadow = (node: Foo) => { let parent = node.parent; return parent; };')).toReport(
      'destructureParameterNoFix',
    );
  });

  test('8.2.3 reports a collision with a nested-scope binding without offering an autofix', ({ lintRule }) => {
    expect(lintRule('const each = (node: Foo) => node.item.map(item => item);')).toReport('destructureParameterNoFix');
  });
});

describe('8.3 permitting parameters that need their whole object', () => {
  test('8.3.1 leaves an untyped parameter alone', ({ lintRule }) => {
    expect(lintRule('const inferred = (node) => node.parent;')).toReportNothing();
  });

  test('8.3.2 leaves two parameters that would destructure to the same name alone', ({ lintRule }) => {
    expect(lintRule('const pairwise = (left: Foo, right: Foo) => left.member === right.member;')).toReportNothing();
  });

  test('8.3.3 leaves a whole object that is returned, passed on, or compared alone', ({ lintRule }) => {
    expect(lintRule('const identity = (node: Foo) => node;')).toReportNothing();
    expect(lintRule('const pass = (node: Foo) => use(node);')).toReportNothing();
    expect(lintRule('const both = (node: Foo) => node.x === node;')).toReportNothing();
  });

  test('8.3.4 leaves method calls, computed access, and optional access alone', ({ lintRule }) => {
    expect(lintRule('const call = (node: Foo) => node.run();')).toReportNothing();
    expect(lintRule('const indexed = (node: Foo, key: string) => node[key];')).toReportNothing();
    expect(lintRule('const maybe = (node: Foo) => node?.parent;')).toReportNothing();
  });

  test('8.3.5 leaves member writes, reserved-word properties, and already-destructured parameters alone', ({
    lintRule,
  }) => {
    expect(lintRule('const write = (node: Foo) => { node.x = 1; };')).toReportNothing();
    expect(lintRule('const reserved = (node: Foo) => node.default;')).toReportNothing();
    expect(lintRule('const destructured = ({ parent }: Foo) => parent;')).toReportNothing();
  });

  test('8.3.6 leaves an unused parameter and a free-variable capture alone', ({ lintRule }) => {
    expect(lintRule('const unused = (node: Foo) => 1;')).toReportNothing();
    expect(
      lintRule(['const capture = (node: Foo) => {', '  return node.helper + helper();', '};'].join('\n')),
    ).toReportNothing();
  });

  test('8.3.7 leaves a union-typed parameter whose property read depends on narrowing alone', ({ lintRule }) => {
    const code = [
      'type Wide = { kind: "wide"; span: number };',
      'type Slim = { kind: "slim" };',
      'const isWideSpan = (node: Slim | Wide) => node.kind === "wide" && node.span > 0;',
    ].join('\n');
    expect(lintRule(code)).toReportNothing();
  });
});
