import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES } from '@typescript-eslint/utils';
import path from 'node:path';

import { createRule } from '#create-rule';

type MessageId = 'bindingOutsideSeam' | 'moduleOutsideSeam';

const FIXTURES_ALIAS = '#fixtures';
const seamBindings = new Set(['describe', 'expect', 'test']);

const isSeamBinding = (specifier: TSESTree.ImportClause) =>
  specifier.type === AST_NODE_TYPES.ImportSpecifier &&
  (specifier.importKind === 'type' || seamBindings.has(specifier.local.name));

export const testSeamOnlyImports = createRule<[], MessageId>({
  create: context => {
    const directory = path.dirname(context.filename);
    const domain = path.basename(directory);
    const domainSeam =
      domain !== 'stories' && directory.split(path.sep).includes('stories') ? `./${domain}.ts` : undefined;
    const reportsOutsideSeam = (source: null | TSESTree.StringLiteral) => {
      if (source === null || source.value === FIXTURES_ALIAS || source.value === domainSeam) return false;
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
        'Story tests import describe, expect, and test through #fixtures or their local domain module: stories/api tests use ./api.ts. Type imports from that same seam are allowed. Helpers and subjects reach stories through fixture context. Variant tests may be aliased to test. The shipped config covers flat and nested story tests.',
    },
    messages: {
      bindingOutsideSeam:
        'A story test imports only describe, expect, and test from its test seam — expose this as a fixture on the test context instead.',
      moduleOutsideSeam:
        'A story test imports only from #fixtures or its local domain module (stories/api uses ./api.ts) — expose this through fixture context instead.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'test-seam-only-imports',
});
