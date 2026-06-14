import type { LooseRuleDefinition } from '@typescript-eslint/utils/ts-eslint';
import type { ESLint } from 'eslint';

import { ESLintUtils } from '@typescript-eslint/utils';

type EslintRule = NonNullable<ESLint.Plugin['rules']>[string];

type StrictCreate = EslintRule['create'];
type StrictVisitor = ReturnType<StrictCreate>;

export const castToEslintRule = (rule: LooseRuleDefinition) => {
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
  return (source.meta === undefined ? { create } : { create, meta: source.meta }) satisfies EslintRule;
};

const ruleCreator = ESLintUtils.RuleCreator(
  name => `https://github.com/zyplux/zyp-cerberus/blob/main/packages/eslint-config/src/rules/${name}.ts`,
);

export const createRule = <Options extends readonly unknown[], MessageIds extends string>(
  config: Parameters<typeof ruleCreator<Options, MessageIds>>[0],
) => {
  const rule = ruleCreator(config);
  return Object.assign(rule, castToEslintRule(rule));
};
