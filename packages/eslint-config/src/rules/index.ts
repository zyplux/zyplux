import preferArrowFunctions from 'eslint-plugin-prefer-arrow-functions';

import { castToEslintRule, type EslintRule } from '#create-rule';

import { noAnonymousParamType } from './syntactic/no-anonymous-param-type';
import { noIdentityCast } from './syntactic/no-identity-cast';
import { noTypePredicate } from './syntactic/no-type-predicate';
import { preferDestructuredParams } from './syntactic/prefer-destructured-params';
import { noReturnArrayPush } from './type-aware/no-return-array-push';
import { noStrayPascalConst } from './type-aware/no-stray-pascal-const';
import { noTypeAnnotations } from './type-aware/no-type-annotations';
import { noUnvalidatedJson } from './type-aware/no-unvalidated-json';
import { noZodCustom } from './type-aware/no-zod-custom';

const upstreamPreferArrowFunctions = preferArrowFunctions.rules['prefer-arrow-functions'];
if (!upstreamPreferArrowFunctions) {
  throw new Error('eslint-plugin-prefer-arrow-functions: "prefer-arrow-functions" rule missing');
}

export const rules: Record<string, EslintRule> = {
  'no-anonymous-param-type': noAnonymousParamType,
  'no-identity-cast': noIdentityCast,
  'no-return-array-push': noReturnArrayPush,
  'no-stray-pascal-const': noStrayPascalConst,
  'no-type-annotations': noTypeAnnotations,
  'no-type-predicate': noTypePredicate,
  'no-unvalidated-json': noUnvalidatedJson,
  'no-zod-custom': noZodCustom,
  'prefer-arrow-functions': castToEslintRule(upstreamPreferArrowFunctions),
  'prefer-destructured-params': preferDestructuredParams,
};
