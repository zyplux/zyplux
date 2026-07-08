import type * as ts from 'typescript';

export const hasZodBrand = (type: ts.Type): boolean => {
  if (type.getProperty('~standard') !== undefined) return true;
  if (type.getProperty('_zod') !== undefined) return true;
  if (type.isUnion()) return type.types.some(member => hasZodBrand(member));
  return false;
};
