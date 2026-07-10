import type { TSESLint, TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

const isDeclaredModuleBlock = (ancestor: TSESTree.Node) =>
  ancestor.type === AST_NODE_TYPES.TSModuleDeclaration && ancestor.declare;

export const typeOverInterface = createRule({
  create: context => ({
    TSInterfaceDeclaration: node => {
      if (context.sourceCode.getAncestors(node).some(ancestor => isDeclaredModuleBlock(ancestor))) return;
      context.report({
        fix: fixer => {
          const nameEnd = node.typeParameters ?? node.id;
          const fixes: TSESLint.RuleFix[] = [];
          const interfaceToken = context.sourceCode.getTokenBefore(node.id);
          if (interfaceToken) {
            fixes.push(
              fixer.replaceText(interfaceToken, 'type'),
              fixer.replaceTextRange([nameEnd.range[1], node.body.range[0]], ' = '),
            );
          }
          for (const heritage of node.extends) {
            fixes.push(fixer.insertTextAfter(node.body, ` & ${context.sourceCode.getText(heritage)}`));
          }
          if (node.parent.type === AST_NODE_TYPES.ExportDefaultDeclaration) {
            fixes.push(
              fixer.removeRange([node.parent.range[0], node.range[0]]),
              fixer.insertTextAfter(node.body, `\nexport default ${node.id.name}`),
            );
          }
          return fixes;
        },
        messageId: 'typeOverInterface',
        node: node.id,
      });
    },
  }),
  defaultOptions: [],
  meta: {
    docs: {
      description:
        "Prefer `type` aliases over `interface`, except inside `declare module`/`declare global` blocks: there an interface merges with the upstream declaration — extending a library's `Matchers`, augmenting globals — which is the one job a `type` alias cannot do. Replaces `@typescript-eslint/consistent-type-definitions` (`type`), which reports augmentation interfaces it cannot fix.",
    },
    fixable: 'code',
    messages: {
      typeOverInterface:
        'Use a `type` alias instead of an `interface` — interfaces are only for declaration merging inside `declare module` blocks.',
    },
    schema: [],
    type: 'suggestion',
  },
  name: 'type-over-interface',
});
