import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

import { hasZodBrand } from './zod-brand';

type MessageId = 'nonSchemaExport';

const typeDeclarationTypes = new Set<TSESTree.Node['type']>([
  AST_NODE_TYPES.TSInterfaceDeclaration,
  AST_NODE_TYPES.TSTypeAliasDeclaration,
]);

export const contractsOnlySchemas = createRule<[], MessageId>({
  create: context => {
    const services = ESLintUtils.getParserServices(context);

    const isSchema = (node: TSESTree.Node) => hasZodBrand(services.getTypeAtLocation(node));

    const checkDeclarators = (declaration: TSESTree.VariableDeclaration) => {
      if (declaration.kind !== 'const') {
        context.report({ messageId: 'nonSchemaExport', node: declaration });
        return;
      }
      for (const declarator of declaration.declarations) {
        if (!isSchema(declarator.id)) context.report({ messageId: 'nonSchemaExport', node: declarator.id });
      }
    };

    const checkNamedExport = (node: TSESTree.ExportNamedDeclaration) => {
      if (node.exportKind === 'type') return;
      const { declaration } = node;
      if (declaration === null) {
        for (const specifier of node.specifiers) {
          if (specifier.exportKind === 'type') continue;
          if (!isSchema(specifier.local)) context.report({ messageId: 'nonSchemaExport', node: specifier });
        }
        return;
      }
      if (typeDeclarationTypes.has(declaration.type)) return;
      if (declaration.type === AST_NODE_TYPES.VariableDeclaration) {
        checkDeclarators(declaration);
        return;
      }
      context.report({ messageId: 'nonSchemaExport', node: declaration });
    };

    return {
      ExportAllDeclaration: node => {
        if (node.exportKind !== 'type') context.report({ messageId: 'nonSchemaExport', node });
      },
      ExportDefaultDeclaration: node => {
        if (!isSchema(node.declaration)) context.report({ messageId: 'nonSchemaExport', node });
      },
      ExportNamedDeclaration: checkNamedExport,
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description:
        'Keep a contracts module (`src/contracts.ts`) to a schemas-only export surface: every exported value — named, re-exported, or default — must be a zod schema, verified through the type checker by the Standard Schema brand (`~standard`/`_zod`), so schemas built by composition, local helpers, or imported factories are recognized. Type(-only) exports are free. Everything non-exported is the module’s own business: imports from any module, local declarations, and statements go unchecked, so schemas may be computed from implementation vocabulary. A value `export *` is reported wholesale because its surface cannot be verified per name — use named re-exports; mutable exported bindings (`export let`) are reported since a contract must be stable. What this guarantees consumers: importing a contracts module only ever hands them schemas and types, never implementation.',
      requiresTypeChecking: true,
    },
    messages: {
      nonSchemaExport: 'A contracts module exports only zod schemas and types — move this export out of the contract.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'contracts-only-schemas',
});
