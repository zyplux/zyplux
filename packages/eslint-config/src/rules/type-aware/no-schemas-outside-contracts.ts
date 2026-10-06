import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';
import { createNodeSchemaCheck } from '#rule-support/schema-checks';

type MessageId = 'schemaExport';

export const noSchemasOutsideContracts = createRule<[], MessageId>({
  create: context => {
    const isSchema = createNodeSchemaCheck(ESLintUtils.getParserServices(context));
    const reportSchema = (node: TSESTree.Node) => {
      if (isSchema(node)) context.report({ messageId: 'schemaExport', node });
    };

    return {
      ExportDefaultDeclaration: node => {
        reportSchema(node.declaration);
      },
      ExportNamedDeclaration: node => {
        if (node.exportKind === 'type') return;
        if (node.declaration?.type === AST_NODE_TYPES.VariableDeclaration) {
          for (const declarator of node.declaration.declarations) reportSchema(declarator.id);
          return;
        }
        if (node.declaration !== null) return;
        for (const specifier of node.specifiers) {
          if (specifier.exportKind !== 'type') reportSchema(specifier.local);
        }
      },
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description:
        'Keep schema value exports on contracts modules while leaving implementation alone: zod imports, local schema declarations, schema composition, and schema use are unrestricted. Named and default exports of schemas or schema-only plain objects from ordinary modules are reported through the Standard Schema brand (`~standard`/`_zod`). The shipped config exempts `src/contracts.ts` and its `src/contracts/**` child modules; repository-level package-boundary tests remain responsible for deciding which files are public.',
      requiresTypeChecking: true,
    },
    messages: {
      schemaExport:
        'Export Zod schemas and schema collections through a contracts module, not an implementation module.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'no-schemas-outside-contracts',
});
