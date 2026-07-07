import { preferDestructuredParams } from '#rules/prefer-destructured-params';

import { ruleTester } from './rule-tester';

ruleTester.run('prefer-destructured-params', preferDestructuredParams, {
  invalid: [
    {
      code: 'const first = (node: Foo) => node.parent;',
      errors: [{ messageId: 'destructureParameter' }],
      name: 'single property read in a concise body',
      output: 'const first = ({ parent }: Foo) => parent;',
    },
    {
      code: 'const sum = (node: Foo) => node.a + node.b;',
      errors: [{ messageId: 'destructureParameter' }],
      name: 'several distinct properties become several bindings',
      output: 'const sum = ({ a, b }: Foo) => a + b;',
    },
    {
      code: 'const twice = (node: Foo) => node.x + node.x;',
      errors: [{ messageId: 'destructureParameter' }],
      name: 'a property read twice yields a single binding',
      output: 'const twice = ({ x }: Foo) => x + x;',
    },
    {
      code: 'function read(node: Foo) { return node.value; }',
      errors: [{ messageId: 'destructureParameter' }],
      name: 'function declaration parameter',
      output: 'function read({ value }: Foo) { return value; }',
    },
    {
      code: 'const obj = { read(node: Foo) { return node.value; } };',
      errors: [{ messageId: 'destructureParameter' }],
      name: 'object-method parameter',
      output: 'const obj = { read({ value }: Foo) { return value; } };',
    },
    {
      code: ['const getName = (node: Foo) => {', '  const parent = node.parent;', '  return parent.id;', '};'].join('\n'),
      errors: [{ messageId: 'destructureParameter' }],
      name: 'const alias whose name already matches the property is absorbed',
      output: ['const getName = ({ parent }: Foo) => {', '  return parent.id;', '};'].join('\n'),
    },
    {
      code: ['const check = (node: Foo) => {', '  const decl = node.parent;', '  return decl.type && decl.id;', '};'].join('\n'),
      errors: [{ messageId: 'destructureParameter' }],
      name: 'const alias under a different name is absorbed and its references are renamed to the property',
      output: ['const check = ({ parent }: Foo) => {', '  return parent.type && parent.id;', '};'].join('\n'),
    },
    {
      code: ['const mix = (node: Foo) => {', '  const x = node.x;', '  return x + node.y;', '};'].join('\n'),
      errors: [{ messageId: 'destructureParameter' }],
      name: 'an alias and a direct read combine into one pattern',
      output: ['const mix = ({ x, y }: Foo) => {', '  return x + y;', '};'].join('\n'),
    },
    {
      code: 'const keep = (node: Foo) => { let x = node.y; return x; };',
      errors: [{ messageId: 'destructureParameter' }],
      name: 'a non-const alias is treated as a direct read, leaving the local binding in place',
      output: 'const keep = ({ y }: Foo) => { let x = y; return x; };',
    },
    {
      code: [
        'const reExported = (node: Foo, set: Bar) => {',
        '  if (set.size === 0) return false;',
        '  const decl = node.parent;',
        '  return decl.type && set.has(decl.id);',
        '};',
      ].join('\n'),
      errors: [{ messageId: 'destructureParameter' }],
      name: 'only the property-only parameter is destructured; a method-receiver parameter is left alone',
      output: [
        'const reExported = ({ parent }: Foo, set: Bar) => {',
        '  if (set.size === 0) return false;',
        '  return parent.type && set.has(parent.id);',
        '};',
      ].join('\n'),
    },
    {
      code: ['const collide = (node: Foo) => {', '  const parent = 1;', '  return node.parent + parent;', '};'].join('\n'),
      errors: [{ messageId: 'destructureParameterNoFix' }],
      name: 'a property-only parameter still reports when destructuring would collide with a function-scoped local, but offers no autofix',
    },
    {
      code: 'const shadow = (node: Foo) => { let parent = node.parent; return parent; };',
      errors: [{ messageId: 'destructureParameterNoFix' }],
      name: 'a property-only parameter still reports when a same-named local alias would clash, but offers no autofix',
    },
    {
      code: 'const each = (node: Foo) => node.item.map(item => item);',
      errors: [{ messageId: 'destructureParameterNoFix' }],
      name: 'a collision with a nested-scope binding (callback parameter) reports without an autofix',
    },
  ],
  valid: [
    {
      code: 'const inferred = (node) => node.parent;',
      name: 'a parameter without a type annotation (e.g. an inline callback) is left alone',
    },
    {
      code: 'const pairwise = (left: Foo, right: Foo) => left.member === right.member;',
      name: 'two parameters that would both destructure to the same name cannot both be rewritten',
    },
    {
      code: 'const identity = (node: Foo) => node;',
      name: 'the whole object is returned',
    },
    {
      code: 'const pass = (node: Foo) => use(node);',
      name: 'the whole object is passed as an argument',
    },
    {
      code: 'const both = (node: Foo) => node.x === node;',
      name: 'the object is read both as a property owner and as a whole',
    },
    {
      code: 'const call = (node: Foo) => node.run();',
      name: 'a called property is a method that needs its receiver',
    },
    {
      code: 'const indexed = (node: Foo, key: string) => node[key];',
      name: 'computed access cannot be destructured to a fixed name',
    },
    {
      code: 'const maybe = (node: Foo) => node?.parent;',
      name: 'optional access guards a possibly-nullish whole object',
    },
    {
      code: 'const write = (node: Foo) => { node.x = 1; };',
      name: 'writing through the member would not be reproduced by a destructured binding',
    },
    {
      code: 'const reserved = (node: Foo) => node.default;',
      name: 'a reserved word cannot become a binding name',
    },
    {
      code: 'const destructured = ({ parent }: Foo) => parent;',
      name: 'an already-destructured parameter has nothing to rewrite',
    },
    {
      code: 'const unused = (node: Foo) => 1;',
      name: 'an unused parameter has no properties to pull out',
    },
    {
      code: ['const capture = (node: Foo) => {', '  return node.helper + helper();', '};'].join('\n'),
      name: 'destructuring would capture a free variable of the same name, so the parameter is left alone entirely',
    },
  ],
});
