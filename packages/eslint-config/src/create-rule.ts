import type { LooseRuleDefinition, RuleModule } from '@typescript-eslint/utils/ts-eslint';
import type { ESLint } from 'eslint';

import { ESLintUtils } from '@typescript-eslint/utils';

export type EslintRule = NonNullable<ESLint.Plugin['rules']>[string];

type StrictCreate = EslintRule['create'];
type StrictVisitor = ReturnType<StrictCreate>;

export const castToEslintRule = (rule: LooseRuleDefinition): EslintRule => {
  const source = typeof rule === 'function' ? { create: rule } : rule;
  if (typeof source.create !== 'function') {
    throw new TypeError('castToEslintRule: rule is missing a callable `create` method');
  }
  const looseCreate = source.create.bind(source);
  const create: StrictCreate = context => {
    const loose = looseCreate(context);
    const visitor: StrictVisitor = {};
    for (const [key, fn] of Object.entries(loose)) {
      if (typeof fn === 'function') {
        visitor[key] = (...args) => {
          Reflect.apply(fn, undefined, args);
        };
      }
    }
    return visitor;
  };
  return source.meta === undefined ? { create } : { create, meta: source.meta };
};

const ruleCreator = ESLintUtils.RuleCreator<{ requiresTypeChecking?: boolean }>(
  () => 'https://github.com/zyplux/zyplux/tree/main/packages/eslint-config/src/rules',
);

export type CreatedRule<Options extends readonly unknown[], MessageIds extends string> = EslintRule &
  RuleModule<MessageIds, Options>;

export const createRule = <Options extends readonly unknown[], MessageIds extends string>(
  config: Parameters<typeof ruleCreator<Options, MessageIds>>[0],
): CreatedRule<Options, MessageIds> => {
  const rule = ruleCreator(config);
  return Object.assign(rule, castToEslintRule(rule));
};
