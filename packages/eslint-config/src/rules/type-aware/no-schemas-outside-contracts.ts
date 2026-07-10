import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';
import * as ts from 'typescript';

import { createRule } from '#create-rule';

import { hasZodBrand } from './zod-brand';

const ZOD_MODULE = 'zod';

type MessageId = 'schemaConstruction' | 'schemaDeclaration' | 'zodValueImport';

const hasStandardSchemaBrand = (type: ts.Type) => type.getProperty('~standard') !== undefined;

export const noSchemasOutsideContracts = createRule<[], MessageId>({
  create: context => {
    const services = ESLintUtils.getParserServices(context);
    const checker = services.program.getTypeChecker();

    const isSchema = (node: TSESTree.Node) => hasZodBrand(services.getTypeAtLocation(node));

    const isNamespaceBinding = (local: TSESTree.Identifier) => {
      const imported = checker.getSymbolAtLocation(services.esTreeNodeToTSNodeMap.get(local));
      if (imported === undefined) return false;
      const target = (imported.flags & ts.SymbolFlags.Alias) === 0 ? imported : checker.getAliasedSymbol(imported);
      return (target.flags & ts.SymbolFlags.ValueModule) !== 0;
    };

    const buildsSchemas = ({ local, type }: TSESTree.ImportClause) => {
      if (type !== AST_NODE_TYPES.ImportSpecifier) return true;
      if (isNamespaceBinding(local)) return true;
      const bindingType = services.getTypeAtLocation(local);
      if (hasStandardSchemaBrand(bindingType)) return true;
      return [...bindingType.getCallSignatures(), ...bindingType.getConstructSignatures()].some(signature =>
        hasStandardSchemaBrand(signature.getReturnType()),
      );
    };

    const reportsAtAncestor = ({ parent }: TSESTree.CallExpression) => {
      let current: TSESTree.Node | undefined = parent;
      while (current !== undefined) {
        if (current.type === AST_NODE_TYPES.VariableDeclarator) return isSchema(current.id);
        if (current.type === AST_NODE_TYPES.CallExpression && isSchema(current)) return true;
        current = current.parent;
      }
      return false;
    };

    return {
      CallExpression: node => {
        if (!isSchema(node) || reportsAtAncestor(node)) return;
        context.report({ messageId: 'schemaConstruction', node });
      },
      ImportDeclaration: node => {
        if (node.source.value !== ZOD_MODULE || node.importKind === 'type') return;
        for (const specifier of node.specifiers) {
          if (specifier.type === AST_NODE_TYPES.ImportSpecifier && specifier.importKind === 'type') continue;
          if (buildsSchemas(specifier)) context.report({ messageId: 'zodValueImport', node: specifier });
        }
      },
      VariableDeclarator: node => {
        if (isSchema(node.id)) context.report({ messageId: 'schemaDeclaration', node: node.id });
      },
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description:
        'Keep zod schema construction inside the contracts module (`src/contracts.ts`): everywhere else, importing a zod binding that can build schemas (the `z` namespace or a factory like `object`), declaring a schema `const`, or composing a new schema inline (`Base.extend(…)`, `Item.array()`) is reported — import the finished schema from a contracts module instead. Type-aware: a value counts as a schema when its type carries the Standard Schema brand (`~standard`/`_zod`), so compositions from imported schemas are caught without any zod import in the file; an import binding counts as schema-building when it is the zod namespace or its call/construct signatures return a `~standard`-branded value, so non-building values like `ZodError` stay importable. Using schemas stays free — passing them to parsers, calling `.parse`/`.safeParse`, `import type` of zod types, and `z.infer` type references all pass. Inner calls of a construction chain and initializers of a reported declaration are not re-reported. Complement of `contracts-only-schemas`, which holds the contracts module itself to a schemas-only export surface; the shipped config applies this rule to every TypeScript file and exempts the contracts module.',
      requiresTypeChecking: true,
    },
    messages: {
      schemaConstruction:
        'Schemas are composed only in a contracts module (src/contracts.ts) — declare this schema there and import the result.',
      schemaDeclaration:
        'Schemas live only in a contracts module (src/contracts.ts) — declare this schema there and import it.',
      zodValueImport:
        'Only a contracts module (src/contracts.ts) imports zod bindings that build schemas — use `import type` for zod types here and import finished schemas from the contracts module.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'no-schemas-outside-contracts',
});
