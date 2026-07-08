import type { TSESTree } from '@typescript-eslint/utils';
import type * as ts from 'typescript';

import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

import { hasZodBrand } from './zod-brand';

const ZOD_MODULE = 'zod';

type MessageId = 'forbiddenStatement' | 'nonSchemaConst' | 'nonSchemaExport' | 'nonZodImport';

const typeDeclarationTypes = new Set<TSESTree.Node['type']>([
  AST_NODE_TYPES.TSInterfaceDeclaration,
  AST_NODE_TYPES.TSTypeAliasDeclaration,
]);

const buildsSchemas = (type: ts.Type) => {
  const signatures = type.getCallSignatures();
  return signatures.length > 0 && signatures.every(signature => hasZodBrand(signature.getReturnType()));
};

export const contractsOnlySchemas = createRule<[], MessageId>({
  create: context => {
    const services = ESLintUtils.getParserServices(context);

    const isSchema = (node: TSESTree.Node) => hasZodBrand(services.getTypeAtLocation(node));

    const checkModuleSource = ({ source }: TSESTree.ExportAllDeclaration | TSESTree.ExportNamedDeclaration) => {
      if (source !== null && source.value !== ZOD_MODULE) {
        context.report({ messageId: 'nonZodImport', node: source });
      }
    };

    const checkDeclarators = (declaration: TSESTree.VariableDeclaration, messageId: MessageId) => {
      if (declaration.kind !== 'const') {
        context.report({ messageId, node: declaration });
        return;
      }
      for (const declarator of declaration.declarations) {
        if (!isSchema(declarator.id)) context.report({ messageId, node: declarator.id });
      }
    };

    const checkLocalDeclaration = (declaration: TSESTree.VariableDeclaration) => {
      if (declaration.kind !== 'const') {
        context.report({ messageId: 'nonSchemaConst', node: declaration });
        return;
      }
      for (const declarator of declaration.declarations) {
        const type = services.getTypeAtLocation(declarator.id);
        if (!hasZodBrand(type) && !buildsSchemas(type)) {
          context.report({ messageId: 'nonSchemaConst', node: declarator.id });
        }
      }
    };

    const checkNamedExport = (node: TSESTree.ExportNamedDeclaration) => {
      checkModuleSource(node);
      if (node.exportKind === 'type') return;
      const { declaration } = node;
      if (declaration === null) {
        for (const specifier of node.specifiers) {
          if (specifier.exportKind === 'type' || node.source !== null) continue;
          if (!isSchema(specifier.local)) context.report({ messageId: 'nonSchemaExport', node: specifier });
        }
        return;
      }
      if (typeDeclarationTypes.has(declaration.type)) return;
      if (declaration.type === AST_NODE_TYPES.VariableDeclaration) {
        checkDeclarators(declaration, 'nonSchemaExport');
        return;
      }
      context.report({ messageId: 'nonSchemaExport', node: declaration });
    };

    const checkStatement = (statement: TSESTree.Statement) => {
      switch (statement.type) {
        case AST_NODE_TYPES.ExportAllDeclaration: {
          checkModuleSource(statement);
          return;
        }
        case AST_NODE_TYPES.ExportNamedDeclaration: {
          checkNamedExport(statement);
          return;
        }
        case AST_NODE_TYPES.ImportDeclaration: {
          if (statement.source.value !== ZOD_MODULE) {
            context.report({ messageId: 'nonZodImport', node: statement.source });
          }
          return;
        }
        case AST_NODE_TYPES.TSInterfaceDeclaration:
        case AST_NODE_TYPES.TSTypeAliasDeclaration: {
          return;
        }
        case AST_NODE_TYPES.VariableDeclaration: {
          checkLocalDeclaration(statement);
          return;
        }
        default: {
          context.report({ messageId: 'forbiddenStatement', node: statement });
        }
      }
    };

    return {
      Program: node => {
        for (const statement of node.body) checkStatement(statement);
      },
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description:
        'Keep a contracts module (`src/contracts.ts`) declarative: only zod imports, exported zod schema consts, type(-only) exports, and non-exported schema consts or schema-building helper functions. Type-aware: a value counts as a schema when its type carries the Standard Schema brand (`~standard`/`_zod`), so schemas built by composition or local factories are recognized; a non-exported helper is allowed when every call signature returns a schema. Anything else — imports from other modules, exported functions/classes/plain values, side-effecting statements — is reported, keeping contracts consumable by any runtime without dragging in implementation dependencies.',
      requiresTypeChecking: true,
    },
    messages: {
      forbiddenStatement:
        'A contracts module contains only zod imports, zod schema consts, and type exports — move this statement out of the contract.',
      nonSchemaConst:
        'A non-exported declaration in a contracts module must be a `const` zod schema or a schema-building helper — move anything else out of the contract.',
      nonSchemaExport:
        'A contracts module exports only `const` zod schemas and types — move this export out of the contract.',
      nonZodImport:
        "A contracts module may import only from 'zod' — anything else couples the contract to an implementation.",
    },
    schema: [],
    type: 'problem',
  },
  name: 'contracts-only-schemas',
});
