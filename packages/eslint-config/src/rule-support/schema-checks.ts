import type { ParserServicesWithTypeInformation, TSESTree } from '@typescript-eslint/utils';

import * as ts from 'typescript';

const isSchemaType = (
  type: ts.Type,
  checker: ts.TypeChecker,
  node: ts.Node,
  ancestors = new Set<ts.Type>(),
): boolean => {
  if (ancestors.has(type)) return false;
  if (type.isUnion()) return type.types.every(member => isSchemaType(member, checker, node, ancestors));
  if (type.getProperty('~standard') !== undefined || type.getProperty('_zod') !== undefined) return true;
  if (
    !(type.flags & ts.TypeFlags.Object) ||
    type.isClass() ||
    type.getCallSignatures().length > 0 ||
    type.getConstructSignatures().length > 0 ||
    checker.getIndexInfosOfType(type).length > 0
  )
    return false;
  const properties = type.getProperties();
  const parents = new Set(ancestors).add(type);
  return (
    properties.length > 0 &&
    properties.every(
      property =>
        !(property.flags & ts.SymbolFlags.Optional) &&
        isSchemaType(checker.getTypeOfSymbolAtLocation(property, node), checker, node, parents),
    )
  );
};

export const createTypeSchemaCheck = (checker: ts.TypeChecker) => (type: ts.Type, node: ts.Node) =>
  isSchemaType(type, checker, node);

export const createNodeSchemaCheck = (services: ParserServicesWithTypeInformation) => {
  const isSchema = createTypeSchemaCheck(services.program.getTypeChecker());
  return (node: TSESTree.Node) => isSchema(services.getTypeAtLocation(node), services.esTreeNodeToTSNodeMap.get(node));
};
