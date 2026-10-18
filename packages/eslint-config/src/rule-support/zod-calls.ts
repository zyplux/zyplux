import type { ParserServicesWithTypeInformation, TSESTree } from '@typescript-eslint/utils';

import { typeMatchesSomeSpecifier } from '@typescript-eslint/type-utils';
import ts from 'typescript';

export const createZodCallName = (services: ParserServicesWithTypeInformation) => {
  const checker = services.program.getTypeChecker();
  return ({ callee }: TSESTree.CallExpression) => {
    const calleeType = services.getTypeAtLocation(callee);
    const typeName = (calleeType.getSymbol() ?? calleeType.aliasSymbol)?.getName();
    if (
      typeName === undefined ||
      !typeMatchesSomeSpecifier(calleeType, [{ from: 'package', name: typeName, package: 'zod' }], services.program)
    )
      return;
    const symbol = checker.getSymbolAtLocation(services.esTreeNodeToTSNodeMap.get(callee));
    return symbol !== undefined && symbol.flags & ts.SymbolFlags.Alias
      ? checker.getAliasedSymbol(symbol).getName()
      : symbol?.getName();
  };
};
