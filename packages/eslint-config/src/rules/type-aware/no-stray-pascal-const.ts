import type { TSESTree } from '@typescript-eslint/utils';
import type * as ts from 'typescript';

import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

type ExpressionPredicate = (node: TSESTree.Expression) => boolean;

type FactoryChainPredicate = (node: TSESTree.Node, factories: ReadonlySet<string>) => boolean;

type MessageId = 'schemaName' | 'strayPascalConst';

type NoStrayPascalConstOptions = [{ allowedFactories: string[] }];

type StatementPredicate = (statement: TSESTree.Statement) => boolean;

const startsUppercaseExp = /^[A-Z]/;
const lowercaseExp = /[a-z]/;
const schemaNameExp = /^[A-Z][A-Za-z0-9]*Schema$/;
const schemaSuffix = 'Schema';

const jsxTypes = new Set<TSESTree.Node['type']>([AST_NODE_TYPES.JSXElement, AST_NODE_TYPES.JSXFragment]);

const schemaShapedTypes = new Set<TSESTree.Node['type']>([
  AST_NODE_TYPES.CallExpression,
  AST_NODE_TYPES.Identifier,
  AST_NODE_TYPES.MemberExpression,
]);

const defaultFactories = [
  'createContext',
  'createFileRoute',
  'createRootRoute',
  'createServerFn',
  'forwardRef',
  'lazy',
  'memo',
];

const unwrapAssertion = (node: TSESTree.Expression): TSESTree.Expression => {
  if (node.type === AST_NODE_TYPES.TSAsExpression) return unwrapAssertion(node.expression);
  if (node.type === AST_NODE_TYPES.TSNonNullExpression) return unwrapAssertion(node.expression);
  if (node.type === AST_NODE_TYPES.TSSatisfiesExpression) return unwrapAssertion(node.expression);
  return node;
};

const calleeRoot = (node: TSESTree.Node): TSESTree.Node => {
  if (node.type === AST_NODE_TYPES.CallExpression) return calleeRoot(node.callee);
  if (node.type === AST_NODE_TYPES.MemberExpression) return calleeRoot(node.object);
  return node;
};

const isZodRooted = (node: TSESTree.Expression) => {
  const root = calleeRoot(node);
  return root.type === AST_NODE_TYPES.Identifier && root.name === 'z';
};

const hasAllowedFactory: FactoryChainPredicate = (node, factories) => {
  if (node.type === AST_NODE_TYPES.CallExpression) return hasAllowedFactory(node.callee, factories);
  if (node.type === AST_NODE_TYPES.TaggedTemplateExpression) return hasAllowedFactory(node.tag, factories);
  if (node.type === AST_NODE_TYPES.MemberExpression) {
    if (!node.computed && node.property.type === AST_NODE_TYPES.Identifier && factories.has(node.property.name)) {
      return true;
    }
    return hasAllowedFactory(node.object, factories);
  }
  return node.type === AST_NODE_TYPES.Identifier && factories.has(node.name);
};

const isJsxProducing: ExpressionPredicate = node => {
  if (jsxTypes.has(node.type)) return true;
  if (node.type === AST_NODE_TYPES.ConditionalExpression)
    return isJsxProducing(node.consequent) || isJsxProducing(node.alternate);
  if (node.type === AST_NODE_TYPES.LogicalExpression) return isJsxProducing(node.right);
  return false;
};

const hasJsxReturn: StatementPredicate = statement => {
  if (statement.type === AST_NODE_TYPES.ReturnStatement) {
    return statement.argument !== null && isJsxProducing(statement.argument);
  }
  if (statement.type === AST_NODE_TYPES.IfStatement) {
    return hasJsxReturn(statement.consequent) || (statement.alternate !== null && hasJsxReturn(statement.alternate));
  }
  if (statement.type === AST_NODE_TYPES.BlockStatement) return statement.body.some(inner => hasJsxReturn(inner));
  return false;
};

const isComponentInit: ExpressionPredicate = node => {
  if (node.type === AST_NODE_TYPES.ArrowFunctionExpression) {
    if (node.body.type === AST_NODE_TYPES.BlockStatement)
      return node.body.body.some(statement => hasJsxReturn(statement));
    return isJsxProducing(node.body);
  }
  if (node.type === AST_NODE_TYPES.FunctionExpression) return node.body.body.some(statement => hasJsxReturn(statement));
  return false;
};

const hasZodBrand = (type: ts.Type): boolean => {
  if (type.getProperty('~standard') !== undefined) return true;
  if (type.getProperty('_zod') !== undefined) return true;
  if (type.isUnion()) return type.types.some(member => hasZodBrand(member));
  return false;
};

const isPascalCase = (name: string) => startsUppercaseExp.test(name) && lowercaseExp.test(name);

const isValidSchemaName = (name: string) => name.endsWith(schemaSuffix) && schemaNameExp.test(name);

const isSchemaSuspectName = (name: string) => isPascalCase(name) || name.endsWith(schemaSuffix);

export const noStrayPascalConst = createRule<NoStrayPascalConstOptions, MessageId>({
  create: (context, [{ allowedFactories }]) => {
    const services = ESLintUtils.getParserServices(context);
    const factories = new Set([...defaultFactories, ...allowedFactories]);
    const usedAsJsx = new Set<string>();
    const pendingStrays: { id: TSESTree.Identifier; name: string }[] = [];

    const isZodSchemaValue = (value: TSESTree.Expression, isSuspect: boolean) =>
      isZodRooted(value) || (isSuspect && hasZodBrand(services.getTypeAtLocation(value)));

    const checkConst = (id: TSESTree.Identifier, init: TSESTree.Expression) => {
      const { name } = id;
      const value = unwrapAssertion(init);

      if (schemaShapedTypes.has(value.type)) {
        if (isValidSchemaName(name)) return;
        if (isZodSchemaValue(value, isSchemaSuspectName(name))) {
          context.report({ data: { name }, messageId: 'schemaName', node: id });
          return;
        }
      }

      if (!isPascalCase(name)) return;
      if (hasAllowedFactory(value, factories)) return;
      if (isComponentInit(value)) return;
      pendingStrays.push({ id, name });
    };

    const checkDestructuredBinding = (id: TSESTree.Identifier) => {
      const { name } = id;
      if (isValidSchemaName(name) || !isSchemaSuspectName(name)) return;
      if (hasZodBrand(services.getTypeAtLocation(id))) {
        context.report({ data: { name }, messageId: 'schemaName', node: id });
      }
    };

    return {
      JSXOpeningElement: node => {
        let name = node.name;
        while (name.type === AST_NODE_TYPES.JSXMemberExpression) name = name.object;
        if (name.type === AST_NODE_TYPES.JSXIdentifier) usedAsJsx.add(name.name);
      },
      'Program:exit': () => {
        for (const stray of pendingStrays) {
          if (usedAsJsx.has(stray.name)) continue;
          context.report({ data: { name: stray.name }, messageId: 'strayPascalConst', node: stray.id });
        }
      },
      VariableDeclarator: node => {
        if (node.parent.kind !== 'const' || node.init === null) return;
        if (node.id.type === AST_NODE_TYPES.Identifier) {
          checkConst(node.id, node.init);
          return;
        }
        if (node.id.type === AST_NODE_TYPES.ObjectPattern) {
          for (const property of node.id.properties) {
            if (property.type !== AST_NODE_TYPES.Property) continue;
            const binding =
              property.value.type === AST_NODE_TYPES.AssignmentPattern ? property.value.left : property.value;
            if (binding.type === AST_NODE_TYPES.Identifier) checkDestructuredBinding(binding);
          }
        }
      },
    };
  },
  defaultOptions: [{ allowedFactories: [] }],
  meta: {
    docs: {
      description:
        'Restrict PascalCase `const` declarations to the things that warrant them — zod schemas (which must additionally be named `XxxSchema`), React components, and a configurable allowlist of factory calls — and fold in zod schema naming. Type-aware: a value is recognized as a zod schema by its Standard Schema brand (`~standard`/`_zod`) through the type checker, so schemas built by a custom factory, by composition (`Base.partial()`), through an aliased import, or pulled out by destructuring are detected — not only literal `z.…()` construction. Cheap syntactic checks gate the type query: the checker is consulted only for a schema-shaped initializer whose name is already PascalCase- or `Schema`-suspect and is not literally rooted at `z` (recognized syntactically, so every `z.…` schema is caught regardless of name). Any PascalCase const that is not a schema, not a component (an arrow/function returning JSX, or used as a JSX element in the same file), and not produced by an allowed factory (defaults: `createContext`, `createFileRoute`, `createRootRoute`, `createServerFn`, `forwardRef`, `lazy`, `memo`; extend with `allowedFactories`) is reported as a stray. `naming-convention` stays permissive on PascalCase variables; this rule is the semantic gate.',
      requiresTypeChecking: true,
    },
    messages: {
      schemaName:
        'Zod schema `{{name}}` must be PascalCase with a `Schema` suffix (e.g. `UserSchema`); the bare name is reserved for the inferred type (`type User = z.infer<typeof UserSchema>`).',
      strayPascalConst:
        'PascalCase is reserved for zod schemas, React components, and allowed factory results — `{{name}}` is none of these. Use camelCase (or UPPER_CASE for a constant), name it `{{name}}Schema` if it is a schema, or add its factory to `allowedFactories`.',
    },
    schema: [
      {
        additionalProperties: false,
        properties: {
          allowedFactories: { items: { type: 'string' }, type: 'array' },
        },
        type: 'object',
      },
    ],
    type: 'suggestion',
  },
  name: 'no-stray-pascal-const',
});
