import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

type MessageId = 'bindingOutsideSeam' | 'moduleOutsideSeam';

const FIXTURES_ALIAS = '#fixtures';
const seamBindings = new Set(['describe', 'expect', 'test']);

const isSeamBinding = (specifier: TSESTree.ImportClause) =>
  specifier.type === AST_NODE_TYPES.ImportSpecifier &&
  (specifier.importKind === 'type' || seamBindings.has(specifier.local.name));

export const testSeamOnlyImports = createRule<[], MessageId>({
  create: context => {
    const reportsOutsideSeam = (source: null | TSESTree.StringLiteral) => {
      if (source === null || source.value === FIXTURES_ALIAS) return false;
      context.report({ messageId: 'moduleOutsideSeam', node: source });
      return true;
    };

    return {
      ExportAllDeclaration: node => {
        reportsOutsideSeam(node.source);
      },
      ExportNamedDeclaration: node => {
        reportsOutsideSeam(node.source);
      },
      ImportDeclaration: node => {
        if (reportsOutsideSeam(node.source) || node.importKind === 'type') return;
        for (const specifier of node.specifiers) {
          if (!isSeamBinding(specifier)) context.report({ messageId: 'bindingOutsideSeam', node: specifier });
        }
      },
      ImportExpression: ({ source }) => {
        if (source.type === AST_NODE_TYPES.Literal && typeof source.value === 'string') reportsOutsideSeam(source);
      },
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description:
        'Keep story tests behind the test seam: a story test imports only from `#fixtures`, and its value bindings are only `describe`, `expect`, and `test` (a variant test aliased to `test`, like `targetsTest as test`, counts), so the test exercises the public interface through fixture context and survives refactors. Type-only imports from `#fixtures` are free — the fixture types are part of the seam surface. Everything else is reported: any other module (node builtins, third-party, workspace packages, file paths — static, dynamic, or re-exported) and any other value binding from `#fixtures`; helpers, sample data, and matchers reach a story as fixtures on the test context instead. In-editor complement of the cerberus `cli_ts_test_seam`/`lib_ts_test_seam` bites; the shipped config scopes this rule to `**/stories/*.test.{ts,tsx}`.',
    },
    messages: {
      bindingOutsideSeam:
        'A story test imports only `describe`, `expect`, and `test` from `#fixtures` — expose this as a fixture on the test context instead.',
      moduleOutsideSeam:
        'A story test imports only from `#fixtures` — expose what this module provides as a fixture on the test context instead.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'test-seam-only-imports',
});
