import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

type FunctionNode = TSESTree.ArrowFunctionExpression | TSESTree.FunctionDeclaration | TSESTree.FunctionExpression;

const anonymousObjectTypesIn = (typeNode: TSESTree.TypeNode): TSESTree.TSTypeLiteral[] => {
  if (typeNode.type === AST_NODE_TYPES.TSTypeLiteral) return [typeNode];
  return typeNode.type === AST_NODE_TYPES.TSUnionType || typeNode.type === AST_NODE_TYPES.TSIntersectionType
    ? typeNode.types.flatMap(member => anonymousObjectTypesIn(member))
    : [];
};

const parameterAnnotation = (param: TSESTree.Parameter) => {
  let binding: TSESTree.Node = param;
  while (binding.type === AST_NODE_TYPES.AssignmentPattern || binding.type === AST_NODE_TYPES.TSParameterProperty) {
    binding = binding.type === AST_NODE_TYPES.AssignmentPattern ? binding.left : binding.parameter;
  }
  return 'typeAnnotation' in binding ? binding.typeAnnotation : undefined;
};

export const noAnonymousParamType = createRule({
  create: context => {
    const checkFunction = ({ params }: FunctionNode) => {
      for (const param of params) {
        const annotation = parameterAnnotation(param);
        if (!annotation) continue;
        for (const literal of anonymousObjectTypesIn(annotation.typeAnnotation)) {
          context.report({ messageId: 'nameParameterType', node: literal });
        }
      }
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
      description:
        'Disallow inline object type literals (`{ … }`) in function parameter positions; extract the shape into a named `type` alias or `interface` so signatures stay readable and the type is reusable. A literal nested directly in a parameter’s union or intersection type is also flagged (e.g. `{ a } | undefined`, `Base & { a }`); literals inside a container — `{ a }[]`, `Array<{ a }>`, `Record<K, { a }>` — describe the container’s element, not the parameter’s own shape, so they are left alone. No autofix: a meaningful type name cannot be inferred.',
    },
    messages: {
      nameParameterType:
        'Inline object type literal in a parameter; extract it into a named `type` alias or `interface` instead of annotating the parameter with an anonymous shape.',
    },
    schema: [],
    type: 'suggestion',
  },
  name: 'no-anonymous-param-type',
});
