import type { TSESTree } from '@typescript-eslint/utils';

import { ESLintUtils } from '@typescript-eslint/utils';
import unicorn from 'eslint-plugin-unicorn';

import { createRule } from '#create-rule';
import { createNodeSchemaCheck } from '#rule-support/schema-checks';

const upstream = unicorn.rules?.['max-nested-calls'];
if (!upstream) throw new Error('eslint-plugin-unicorn: "max-nested-calls" rule missing');
const createUpstream = upstream.create.bind(upstream);

export const maxNestedCalls = createRule<[{ max: number }], 'max-nested-calls'>({
  create: context => {
    const isSchema = createNodeSchemaCheck(ESLintUtils.getParserServices(context));
    const upstreamListeners: unknown = Reflect.apply(createUpstream, undefined, [context]);
    if (upstreamListeners === null || typeof upstreamListeners !== 'object') {
      throw new TypeError('eslint-plugin-unicorn: expected nesting rule listeners');
    }
    const listeners: Record<string, (...args: unknown[]) => void> = {};
    for (const [selector, candidate] of Object.entries(upstreamListeners)) {
      const listener: unknown = candidate;
      if (typeof listener !== 'function') continue;
      listeners[selector] = (...args) => {
        Reflect.apply(listener, undefined, args);
      };
    }
    const checkCall = (node: TSESTree.CallExpression | TSESTree.NewExpression) => {
      if (!isSchema(node)) listeners[node.type]?.(node);
    };
    return { ...listeners, CallExpression: checkCall, NewExpression: checkCall };
  },
  defaultOptions: [{ max: 3 }],
  meta: {
    defaultOptions: [{ max: 3 }],
    docs: {
      description: 'Run Unicorn nesting checks while exempting calls that return Zod schemas.',
      requiresTypeChecking: true,
    },
    messages: { 'max-nested-calls': 'Call is nested too deeply. Maximum allowed is {{max}}.' },
    schema: [{ additionalProperties: false, properties: { max: { minimum: 1, type: 'integer' } }, type: 'object' }],
    type: 'suggestion',
  },
  name: 'max-nested-calls',
});
