import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

import { hasZodBrand } from './zod-brand';

const ZOD_MODULE = 'zod';

type MessageId = 'schemaConstruction' | 'schemaDeclaration' | 'zodValueImport';

const hasValueBindings = ({ specifiers }: TSESTree.ImportDeclaration) =>
  specifiers.some(specifier => specifier.type !== AST_NODE_TYPES.ImportSpecifier || specifier.importKind !== 'type');

export const noSchemasOutsideContracts = createRule<[], MessageId>({
  create: context => {
    const services = ESLintUtils.getParserServices(context);

    const isSchema = (node: TSESTree.Node) => hasZodBrand(services.getTypeAtLocation(node));

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
        if (node.source.value !== ZOD_MODULE || node.importKind === 'type' || !hasValueBindings(node)) return;
        context.report({ messageId: 'zodValueImport', node: node.source });
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
        'Keep zod schema construction inside the contracts module (`src/contracts.ts`): everywhere else, importing zod as a value, declaring a schema `const`, or composing a new schema inline (`Base.extend(…)`, `Item.array()`) is reported — import the finished schema from a contracts module instead. Type-aware: a value counts as a schema when its type carries the Standard Schema brand (`~standard`/`_zod`), so compositions from imported schemas are caught without any zod import in the file. Using schemas stays free — passing them to parsers, calling `.parse`/`.safeParse`, `import type` of zod types, and `z.infer` type references all pass. Inner calls of a construction chain and initializers of a reported declaration are not re-reported. Complement of `contracts-only-schemas`, which holds the contracts module itself to a schemas-only export surface; the shipped config scopes this rule to source files and exempts `src/contracts.ts`.',
      requiresTypeChecking: true,
    },
    messages: {
      schemaConstruction:
        'Schemas are composed only in a contracts module (src/contracts.ts) — declare this schema there and import the result.',
      schemaDeclaration:
        'Schemas live only in a contracts module (src/contracts.ts) — declare this schema there and import it.',
      zodValueImport:
        'Only a contracts module (src/contracts.ts) imports zod as a value — use `import type` for zod types here and import finished schemas from the contracts module.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'no-schemas-outside-contracts',
});
