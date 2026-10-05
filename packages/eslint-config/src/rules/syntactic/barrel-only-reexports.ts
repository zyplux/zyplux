import { AST_NODE_TYPES } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

export const barrelOnlyReexports = createRule({
  create: context => ({
    Program: ({ body }) => {
      for (const node of body) {
        if (
          (node.type === AST_NODE_TYPES.ExportNamedDeclaration || node.type === AST_NODE_TYPES.ExportAllDeclaration) &&
          node.source !== null
        )
          continue;
        context.report({ messageId: 'statement', node });
      }
    },
  }),
  defaultOptions: [],
  meta: {
    docs: { description: 'Public barrels contain only re-exports.' },
    messages: { statement: 'A public barrel contains only re-exports; move this statement to its owning module.' },
    schema: [],
    type: 'problem',
  },
  name: 'barrel-only-reexports',
});
