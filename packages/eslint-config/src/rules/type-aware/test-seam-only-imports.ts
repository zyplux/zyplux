import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

type MessageId = 'pathImport' | 'workspaceImport';

const seamSpecifierPrefixes = ['#', 'node:'];
const pathSpecifierPrefixes = ['.', '/'];

export const testSeamOnlyImports = createRule<[], MessageId>({
  create: context => {
    const services = ESLintUtils.getParserServices(context);
    const checker = services.program.getTypeChecker();

    const resolvesToWorkspaceSource = (source: TSESTree.StringLiteral) => {
      const symbol = checker.getSymbolAtLocation(services.esTreeNodeToTSNodeMap.get(source));
      const declaration = symbol?.valueDeclaration ?? symbol?.declarations?.[0];
      if (declaration === undefined) return false;
      const file = declaration.getSourceFile();
      return !file.fileName.includes('/node_modules/') && !file.isDeclarationFile;
    };

    const checkModuleSource = (source: null | TSESTree.StringLiteral) => {
      if (source === null) return;
      const specifier = source.value;
      if (seamSpecifierPrefixes.some(prefix => specifier.startsWith(prefix))) return;
      if (pathSpecifierPrefixes.some(prefix => specifier.startsWith(prefix))) {
        context.report({ messageId: 'pathImport', node: source });
        return;
      }
      if (resolvesToWorkspaceSource(source)) context.report({ messageId: 'workspaceImport', node: source });
    };

    return {
      ExportAllDeclaration: node => {
        checkModuleSource(node.source);
      },
      ExportNamedDeclaration: node => {
        checkModuleSource(node.source);
      },
      ImportDeclaration: node => {
        checkModuleSource(node.source);
      },
      ImportExpression: ({ source }) => {
        if (source.type === AST_NODE_TYPES.Literal && typeof source.value === 'string') checkModuleSource(source);
      },
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description:
        'Keep story tests behind the test seam: a story test reaches workspace code only through `#` fixture aliases, so it exercises the public interface and survives refactors. Imports of `#` aliases and `node:` builtins pass, and so do third-party modules — they cannot touch package internals; the rule resolves each remaining specifier through the type checker and reports it when it lands on workspace source (relative and absolute path specifiers are reported outright). Type-only imports count too: naming an internal type couples the test to internals just the same. In-editor complement of the cerberus `cli_ts_test_seam`/`lib_ts_test_seam` bites; the shipped config scopes this rule to `**/stories/*.test.{ts,tsx}`.',
      requiresTypeChecking: true,
    },
    messages: {
      pathImport:
        'A story test reaches workspace code only through the test seam — replace this file-path import with a `#` fixtures alias.',
      workspaceImport:
        'A story test reaches workspace code only through the test seam — expose this through the fixtures package and import it via a `#` alias.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'test-seam-only-imports',
});
