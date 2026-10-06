import { ESLintUtils } from '@typescript-eslint/utils';
import ts from 'typescript';

import { createRule } from '#create-rule';
import {
  findExportDeclaration,
  hasTypeOnlySpecifier,
  isMutableBinding,
  mapReexportDeclarations,
} from '#rule-support/export-declarations';
import { createTypeSchemaCheck } from '#rule-support/schema-checks';

export const contractsOnlySchemas = createRule({
  create: context => {
    const services = ESLintUtils.getParserServices(context);
    const checker = services.program.getTypeChecker();
    const isSchema = createTypeSchemaCheck(checker);
    const isSchemaExport = (symbol: ts.Symbol) => {
      const declaration = symbol.valueDeclaration ?? symbol.declarations?.[0];
      return (
        declaration !== undefined &&
        !isMutableBinding(declaration) &&
        isSchema(checker.getTypeOfSymbolAtLocation(symbol, declaration), declaration)
      );
    };
    return {
      'Program:exit': node => {
        const source = services.esTreeNodeToTSNodeMap.get(node);
        const module = checker.getSymbolAtLocation(source);
        if (module === undefined) return;
        const reexports = mapReexportDeclarations(source, checker);
        const invalidExports = checker.getExportsOfModule(module).filter(exported => {
          const symbol = exported.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(exported) : exported;
          return (
            !hasTypeOnlySpecifier(exported) &&
            (symbol.flags & ts.SymbolFlags.Value) !== 0 &&
            (exported.declarations?.some(declaration => declaration.getSourceFile() === source) === true ||
              reexports.has(exported.name)) &&
            !isSchemaExport(symbol)
          );
        });
        const locations = new Set(
          invalidExports.map(exported => {
            const local = findExportDeclaration(exported, source, reexports);
            return local === undefined ? node : services.tsNodeToESTreeNodeMap.get(local);
          }),
        );
        for (const location of locations) context.report({ messageId: 'nonSchemaExport', node: location });
      },
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description:
        'Contracts export immutable Zod schemas, schema collections, and types, including resolved re-exports.',
      requiresTypeChecking: true,
    },
    messages: {
      nonSchemaExport:
        'A contracts module exports only Zod schemas, schema collections, and types — move this export out of the contract.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'contracts-only-schemas',
});
