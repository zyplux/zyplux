import type { TypeOrValueSpecifier } from '@typescript-eslint/type-utils';
import type { TSESTree } from '@typescript-eslint/utils';

import { valueMatchesSomeSpecifier } from '@typescript-eslint/type-utils';
import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

const zodCustomSpecifiers: TypeOrValueSpecifier[] = [{ from: 'package', name: 'custom', package: 'zod' }];

const getCalleeNameNode = (callee: TSESTree.Node) => {
  if (callee.type === AST_NODE_TYPES.Identifier) return callee;
  if (callee.type === AST_NODE_TYPES.MemberExpression && !callee.computed && callee.property.type === AST_NODE_TYPES.Identifier) {
    return callee.property;
  }
  return;
};

export const noZodCustom = createRule({
  create: context => {
    const services = ESLintUtils.getParserServices(context);

    return {
      CallExpression: node => {
        const nameNode = getCalleeNameNode(node.callee);
        if (nameNode?.name !== 'custom') return;
        const calleeType = services.getTypeAtLocation(node.callee);
        if (!valueMatchesSomeSpecifier(nameNode, zodCustomSpecifiers, services.program, calleeType)) return;
        context.report({ messageId: 'noZodCustom', node });
      },
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description:
        "Disallow zod's `custom<T>()` — the generic argument is an unverified type assertion that bypasses zod's runtime guarantee. Type-aware: the `custom` callee is resolved to the `zod` package, so an aliased import (`import { z as v }`, `import * as z`) is caught too, while a `custom()` from any other origin is left alone.",
      requiresTypeChecking: true,
    },
    messages: {
      noZodCustom:
        '`z.custom<T>()` is an unverified type assertion (the generic is trusted, not validated). Build the value with real zod combinators (`z.object`, `z.union`, etc.) or restructure to runtime-validate the shape.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'no-zod-custom',
});
