import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

type FunctionLike = TSESTree.ArrowFunctionExpression | TSESTree.FunctionDeclaration | TSESTree.FunctionExpression;

const returnsParameterUnchanged = ({ body }: FunctionLike, parameterName: string) => {
  if (body.type === AST_NODE_TYPES.Identifier) {
    return body.name === parameterName;
  }
  if (body.type !== AST_NODE_TYPES.BlockStatement) return false;
  const [statement, ...rest] = body.body;
  return (
    rest.length === 0 &&
    statement?.type === AST_NODE_TYPES.ReturnStatement &&
    statement.argument?.type === AST_NODE_TYPES.Identifier &&
    statement.argument.name === parameterName
  );
};

export const noIdentityCast = createRule({
  create: context => {
    const checkFunction = (node: FunctionLike) => {
      if (node.typeParameters) return;

      const [parameter, ...rest] = node.params;
      if (rest.length > 0) return;
      if (parameter?.type !== AST_NODE_TYPES.Identifier || !parameter.typeAnnotation) return;

      if (!returnsParameterUnchanged(node, parameter.name)) return;

      context.report({ messageId: 'noIdentityCast', node });
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
      description: 'Disallow concrete-typed identity functions (`(x: T) => x`) — a type assertion in disguise; make a genuine pass-through generic instead.',
    },
    messages: {
      noIdentityCast:
        'A concrete-typed identity function (`(x: T) => x`) only relabels its argument — a type assertion in disguise. For a genuine pass-through make it generic (`<T>(x: T) => x`); to give an inferred value a nameable type use `satisfies` or `export` the type; to trust external data validate it with a zod schema that returns the typed value.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'no-identity-cast',
});
