import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';
import { createNodeSchemaCheck } from '#rule-support/schema-checks';

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
  AST_NODE_TYPES.ObjectExpression,
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
  return node.type === AST_NODE_TYPES.TSSatisfiesExpression ? unwrapAssertion(node.expression) : node;
};

const hasAllowedFactory: FactoryChainPredicate = (node, factories) => {
  if (node.type === AST_NODE_TYPES.CallExpression) return hasAllowedFactory(node.callee, factories);
  if (node.type === AST_NODE_TYPES.TaggedTemplateExpression) return hasAllowedFactory(node.tag, factories);
  return node.type === AST_NODE_TYPES.MemberExpression
    ? (!node.computed && node.property.type === AST_NODE_TYPES.Identifier && factories.has(node.property.name)) ||
        hasAllowedFactory(node.object, factories)
    : node.type === AST_NODE_TYPES.Identifier && factories.has(node.name);
};

const isJsxProducing: ExpressionPredicate = node => {
  if (jsxTypes.has(node.type)) return true;
  return node.type === AST_NODE_TYPES.ConditionalExpression
    ? isJsxProducing(node.consequent) || isJsxProducing(node.alternate)
    : node.type === AST_NODE_TYPES.LogicalExpression && isJsxProducing(node.right);
};

const hasJsxReturn: StatementPredicate = statement => {
  if (statement.type === AST_NODE_TYPES.ReturnStatement) {
    return statement.argument !== null && isJsxProducing(statement.argument);
  }
  return statement.type === AST_NODE_TYPES.IfStatement
    ? hasJsxReturn(statement.consequent) || (statement.alternate !== null && hasJsxReturn(statement.alternate))
    : statement.type === AST_NODE_TYPES.BlockStatement && statement.body.some(inner => hasJsxReturn(inner));
};

const isComponentInit: ExpressionPredicate = node => {
  if (node.type === AST_NODE_TYPES.ArrowFunctionExpression) {
    return node.body.type === AST_NODE_TYPES.BlockStatement
      ? node.body.body.some(statement => hasJsxReturn(statement))
      : isJsxProducing(node.body);
  }
  return node.type === AST_NODE_TYPES.FunctionExpression && node.body.body.some(statement => hasJsxReturn(statement));
};

const isPascalCase = (name: string) => startsUppercaseExp.test(name) && lowercaseExp.test(name);

const isValidSchemaName = (name: string) => name.endsWith(schemaSuffix) && schemaNameExp.test(name);

const isSchemaSuspectName = (name: string) => isPascalCase(name) || name.endsWith(schemaSuffix);

export const noStrayPascalConst = createRule<NoStrayPascalConstOptions, MessageId>({
  create: (context, [{ allowedFactories }]) => {
    const isSchema = createNodeSchemaCheck(ESLintUtils.getParserServices(context));
    const factories = new Set([...defaultFactories, ...allowedFactories]);
    const usedAsJsx = new Set<string>();
    const pendingStrays: { id: TSESTree.Identifier; name: string }[] = [];

    const checkConst = (id: TSESTree.Identifier, init: TSESTree.Expression) => {
      const { name } = id;
      const value = unwrapAssertion(init);

      if (schemaShapedTypes.has(value.type) && isSchema(value)) {
        if (!isValidSchemaName(name)) context.report({ data: { name }, messageId: 'schemaName', node: id });
        return;
      }

      if (!isPascalCase(name) || hasAllowedFactory(value, factories) || isComponentInit(value)) return;
      pendingStrays.push({ id, name });
    };

    const checkDestructuredBinding = (id: TSESTree.Identifier) => {
      const { name } = id;
      if (isValidSchemaName(name) || !isSchemaSuspectName(name)) return;
      if (isSchema(id)) {
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
        'Reserve PascalCase constants for Zod schemas, schema-only plain objects, React components, and allowed factory results. Schemas and schema collections use a Schema suffix. Shared type-aware detection recognizes composition, factories, aliases, and destructured schema values.',
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
