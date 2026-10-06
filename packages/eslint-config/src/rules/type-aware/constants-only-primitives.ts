import { ESLintUtils, type TSESTree } from '@typescript-eslint/utils';
import ts from 'typescript';

import { createRule } from '#create-rule';
import {
  findExportDeclaration,
  hasTypeOnlySpecifier,
  isMutableBinding,
  mapReexportDeclarations,
} from '#rule-support/export-declarations';

const primitiveFlags =
  ts.TypeFlags.StringLike |
  ts.TypeFlags.NumberLike |
  ts.TypeFlags.BooleanLike |
  ts.TypeFlags.BigIntLike |
  ts.TypeFlags.ESSymbolLike |
  ts.TypeFlags.Null |
  ts.TypeFlags.Undefined;
const isPrimitive = (type: ts.Type): boolean =>
  type.isUnion() ? type.types.every(member => isPrimitive(member)) : (type.flags & primitiveFlags) !== 0;

export const constantsOnlyPrimitives = createRule({
  create: context => {
    const services = ESLintUtils.getParserServices(context);
    const checker = services.program.getTypeChecker();
    return {
      'Program:exit': node => {
        const source = services.esTreeNodeToTSNodeMap.get(node);
        const module = checker.getSymbolAtLocation(source);
        if (module === undefined) return;
        const reexports = mapReexportDeclarations(source, checker);
        const reported = new Set<TSESTree.Node>();
        for (const exported of checker.getExportsOfModule(module)) {
          const symbol = exported.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(exported) : exported;
          const declaration = symbol.valueDeclaration;
          if (
            declaration !== undefined &&
            !hasTypeOnlySpecifier(exported) &&
            isPrimitive(checker.getTypeOfSymbolAtLocation(symbol, declaration)) &&
            !isMutableBinding(declaration)
          )
            continue;
          const local = findExportDeclaration(exported, source, reexports);
          const location = local === undefined ? node : services.tsNodeToESTreeNodeMap.get(local);
          if (reported.has(location)) continue;
          reported.add(location);
          context.report({ messageId: 'nonPrimitive', node: location });
        }
      },
    };
  },
  defaultOptions: [],
  meta: {
    docs: { description: 'Constants surfaces export only immutable primitive values.', requiresTypeChecking: true },
    messages: { nonPrimitive: 'A constants surface exports only immutable primitive values.' },
    schema: [],
    type: 'problem',
  },
  name: 'constants-only-primitives',
});
