import preferArrowFunctions from 'eslint-plugin-prefer-arrow-functions';

import { castToEslintRule, type EslintRule } from '#create-rule';

import { fixtureRoleImports } from './syntactic/fixture-role-imports.ts';
import { noAnonymousParamType } from './syntactic/no-anonymous-param-type.ts';
import { noIdentityCast } from './syntactic/no-identity-cast.ts';
import { noTypePredicate } from './syntactic/no-type-predicate.ts';
import { testSeamOnlyImports } from './syntactic/test-seam-only-imports.ts';
import { typeOverInterface } from './syntactic/type-over-interface.ts';
import { contractsOnlySchemas } from './type-aware/contracts-only-schemas.ts';
import { maxNestedCalls } from './type-aware/max-nested-calls.ts';
import { noReturnArrayPush } from './type-aware/no-return-array-push.ts';
import { noSchemasOutsideContracts } from './type-aware/no-schemas-outside-contracts.ts';
import { noStrayPascalConst } from './type-aware/no-stray-pascal-const.ts';
import { noTypeAnnotations } from './type-aware/no-type-annotations.ts';
import { noUnvalidatedJson } from './type-aware/no-unvalidated-json.ts';
import { noZodCustom } from './type-aware/no-zod-custom.ts';
import { preferDestructuredParams } from './type-aware/prefer-destructured-params.ts';

const upstreamPreferArrowFunctions = preferArrowFunctions.rules['prefer-arrow-functions'];
if (!upstreamPreferArrowFunctions) {
  throw new Error('eslint-plugin-prefer-arrow-functions: "prefer-arrow-functions" rule missing');
}

export const rules: Record<string, EslintRule> = {
  'contracts-only-schemas': contractsOnlySchemas,
  'fixture-role-imports': fixtureRoleImports,
  'max-nested-calls': maxNestedCalls,
  'no-anonymous-param-type': noAnonymousParamType,
  'no-identity-cast': noIdentityCast,
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
