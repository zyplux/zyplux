import { AST_NODE_TYPES, type TSESTree } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

const isTypeDeclaration = (node: null | TSESTree.Node) =>
  node?.type === AST_NODE_TYPES.TSInterfaceDeclaration || node?.type === AST_NODE_TYPES.TSTypeAliasDeclaration;

const isTypeStatement = (node: TSESTree.ProgramStatement) => {
  if (isTypeDeclaration(node)) return true;
  switch (node.type) {
    case AST_NODE_TYPES.ExportAllDeclaration: {
      return node.exportKind === 'type';
    }
    case AST_NODE_TYPES.ExportNamedDeclaration: {
      return (
        node.exportKind === 'type' ||
        isTypeDeclaration(node.declaration) ||
        (node.specifiers.length > 0 && node.specifiers.every(specifier => specifier.exportKind === 'type'))
      );
    }
    case AST_NODE_TYPES.ImportDeclaration: {
      return (
        node.importKind === 'type' ||
        (node.specifiers.length > 0 &&
          node.specifiers.every(
            specifier => specifier.type === AST_NODE_TYPES.ImportSpecifier && specifier.importKind === 'type',
          ))
      );
    }
    default: {
      return false;
    }
  }
};

export const typeOnlyModules = createRule({
  create: context => ({
    Program: ({ body }) => {
      for (const node of body) {
        if (!isTypeStatement(node)) context.report({ messageId: 'runtime', node });
      }
    },
  }),
  defaultOptions: [],
  meta: {
    docs: { description: 'Types and interfaces modules contain only type-level statements.' },
    messages: {
      runtime: 'A types/interfaces module contains only type declarations and type-only imports or exports.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'type-only-modules',
});
