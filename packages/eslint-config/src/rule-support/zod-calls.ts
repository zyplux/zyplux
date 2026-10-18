import type { ParserServicesWithTypeInformation, TSESTree } from '@typescript-eslint/utils';

import { typeMatchesSomeSpecifier } from '@typescript-eslint/type-utils';
import ts from 'typescript';

export const createZodTypeCheck =
  ({ program }: ParserServicesWithTypeInformation) =>
  (type: ts.Type) => {
    const name = (type.getSymbol() ?? type.aliasSymbol)?.getName();
    return name !== undefined && typeMatchesSomeSpecifier(type, [{ from: 'package', name, package: 'zod' }], program);
  };

export const createZodCallName = (services: ParserServicesWithTypeInformation) => {
  const checker = services.program.getTypeChecker();
  const isZodType = createZodTypeCheck(services);
  return ({ callee }: TSESTree.CallExpression) => {
    const calleeType = services.getTypeAtLocation(callee);
    if (!isZodType(calleeType)) return;
    const symbol = checker.getSymbolAtLocation(services.esTreeNodeToTSNodeMap.get(callee));
    return symbol !== undefined && symbol.flags & ts.SymbolFlags.Alias
      ? checker.getAliasedSymbol(symbol).getName()
      : symbol?.getName();
  };
};
