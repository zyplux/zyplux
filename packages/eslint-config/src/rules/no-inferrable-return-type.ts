import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES } from '@typescript-eslint/utils';

import { createRule } from '../create-rule';

type FunctionWithReturnType =
  | TSESTree.ArrowFunctionExpression
  | TSESTree.FunctionDeclaration
  | TSESTree.FunctionExpression;

const getFunctionName = (node: FunctionWithReturnType) => {
  if (
    (node.type === AST_NODE_TYPES.FunctionDeclaration || node.type === AST_NODE_TYPES.FunctionExpression) &&
    node.id
  ) {
    return node.id.name;
  }
  const parent = node.parent;
  if (parent.type === AST_NODE_TYPES.VariableDeclarator && parent.id.type === AST_NODE_TYPES.Identifier) {
    return parent.id.name;
  }
  return;
};

const traverse = (node: object, visit: (n: object) => boolean): boolean => {
  if (visit(node)) return true;
  const entries: ReadonlyMap<string, unknown> = new Map(Object.entries(node));
  for (const [key, value] of entries) {
    if (key === 'parent' || key === 'loc' || key === 'range') continue;
    const items: readonly unknown[] = Array.isArray(value) ? value : [value];
    for (const item of items) {
      if (item === null || typeof item !== 'object') continue;
      if (traverse(item, visit)) return true;
    }
  }
  return false;
};

const bodyReferencesIdentifier = (body: TSESTree.Node, name: string) =>
  traverse(body, n => {
    if (!('type' in n) || n.type !== AST_NODE_TYPES.Identifier) return false;
    if (!('name' in n) || typeof n.name !== 'string') return false;
    return n.name === name;
  });

const collectTypeParamNames = (node: FunctionWithReturnType) => {
  const names = new Set<string>();
  if (node.typeParameters) {
    for (const param of node.typeParameters.params) {
      names.add(param.name.name);
    }
  }
  return names;
};

const returnTypeReferencesAny = (typeNode: TSESTree.Node, names: Set<string>) => {
  if (names.size === 0) return false;
  return traverse(typeNode, n => {
    if (!('type' in n) || n.type !== AST_NODE_TYPES.TSTypeReference) return false;
    if (!('typeName' in n) || n.typeName === null || typeof n.typeName !== 'object') return false;
    if (!('type' in n.typeName) || n.typeName.type !== AST_NODE_TYPES.Identifier) return false;
    if (!('name' in n.typeName) || typeof n.typeName.name !== 'string') return false;
    return names.has(n.typeName.name);
  });
};

export const noInferrableReturnType = createRule({
  create: context => {
    const checkFunction = (node: FunctionWithReturnType) => {
      const returnTypeNode = node.returnType;
      if (!returnTypeNode) return;

      if (returnTypeNode.typeAnnotation.type === AST_NODE_TYPES.TSTypePredicate) return;

      const typeParamNames = collectTypeParamNames(node);
      if (returnTypeReferencesAny(returnTypeNode.typeAnnotation, typeParamNames)) return;

      const functionName = getFunctionName(node);
      if (functionName && bodyReferencesIdentifier(node.body, functionName)) return;

      const tokenBefore = context.sourceCode.getTokenBefore(returnTypeNode);
      context.report({
        ...(tokenBefore && {
          fix: fixer => fixer.removeRange([tokenBefore.range[1], returnTypeNode.range[1]]),
        }),
        messageId: 'removeReturnType',
        node: returnTypeNode,
      });
    };

    return {
      ArrowFunctionExpression: checkFunction,
      FunctionDeclaration: checkFunction,
      FunctionExpression: checkFunction,
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description: 'Disallow explicit return type annotations on functions; let TypeScript infer them.',
    },
    fixable: 'code',
    messages: {
      removeReturnType:
        'Explicit return type annotation is unnecessary; let TypeScript infer it. If `tsc` needs it for declaration-emit portability (TS2742/TS2883), annotate the returned value with `satisfies` or export the referenced type instead of annotating the return position.',
    },
    schema: [],
    type: 'suggestion',
  },
  name: 'no-inferrable-return-type',
});
