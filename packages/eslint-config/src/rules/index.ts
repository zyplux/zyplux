import preferArrowFunctions from 'eslint-plugin-prefer-arrow-functions';

import { castToEslintRule, type EslintRule } from '#create-rule';

import { noAnonymousParamType } from './syntactic/no-anonymous-param-type';
import { noIdentityCast } from './syntactic/no-identity-cast';
import { noTypePredicate } from './syntactic/no-type-predicate';
import { testSeamOnlyImports } from './syntactic/test-seam-only-imports';
import { typeOverInterface } from './syntactic/type-over-interface';
import { contractsOnlySchemas } from './type-aware/contracts-only-schemas';
import { noPackageWideUnusedTypes } from './type-aware/no-package-wide-unused-types';
import { noReturnArrayPush } from './type-aware/no-return-array-push';
import { noSchemasOutsideContracts } from './type-aware/no-schemas-outside-contracts';
import { noStrayPascalConst } from './type-aware/no-stray-pascal-const';
import { noTypeAnnotations } from './type-aware/no-type-annotations';
import { noUnvalidatedJson } from './type-aware/no-unvalidated-json';
import { noZodCustom } from './type-aware/no-zod-custom';
import { preferDestructuredParams } from './type-aware/prefer-destructured-params';

const upstreamPreferArrowFunctions = preferArrowFunctions.rules['prefer-arrow-functions'];
if (!upstreamPreferArrowFunctions) {
  throw new Error('eslint-plugin-prefer-arrow-functions: "prefer-arrow-functions" rule missing');
}

export const rules: Record<string, EslintRule> = {
  'contracts-only-schemas': contractsOnlySchemas,
  'no-anonymous-param-type': noAnonymousParamType,
  'no-identity-cast': noIdentityCast,
  'no-package-wide-unused-types': noPackageWideUnusedTypes,
  'no-return-array-push': noReturnArrayPush,
  'no-schemas-outside-contracts': noSchemasOutsideContracts,
  'no-stray-pascal-const': noStrayPascalConst,
  'no-type-annotations': noTypeAnnotations,
  'no-type-predicate': noTypePredicate,
  'no-unvalidated-json': noUnvalidatedJson,
  'no-zod-custom': noZodCustom,
  'prefer-arrow-functions': castToEslintRule(upstreamPreferArrowFunctions),
  'prefer-destructured-params': preferDestructuredParams,
  'test-seam-only-imports': testSeamOnlyImports,
  'type-over-interface': typeOverInterface,
};
