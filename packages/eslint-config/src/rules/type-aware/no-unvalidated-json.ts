import type { TSESTree } from '@typescript-eslint/utils';

import { AnyType, discriminateAnyType } from '@typescript-eslint/type-utils';
import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

const zodParseMethods = new Set<string>(['parse', 'parseAsync', 'safeParse', 'safeParseAsync']);

const isJsonParseCall = ({ callee }: TSESTree.CallExpression) =>
  callee.type === AST_NODE_TYPES.MemberExpression &&
  !callee.computed &&
  callee.object.type === AST_NODE_TYPES.Identifier &&
  callee.object.name === 'JSON' &&
  callee.property.type === AST_NODE_TYPES.Identifier &&
  callee.property.name === 'parse';

const isJsonMethodCall = ({ callee }: TSESTree.CallExpression) =>
  callee.type === AST_NODE_TYPES.MemberExpression && !callee.computed && callee.property.type === AST_NODE_TYPES.Identifier && callee.property.name === 'json';

const isZodParseConsumer = (source: TSESTree.CallExpression) => {
  const consumed = source.parent.type === AST_NODE_TYPES.AwaitExpression ? source.parent : source;
  const { parent: host } = consumed;
  return (
    host.type === AST_NODE_TYPES.CallExpression &&
    host.callee.type === AST_NODE_TYPES.MemberExpression &&
    !host.callee.computed &&
    host.callee.property.type === AST_NODE_TYPES.Identifier &&
    zodParseMethods.has(host.callee.property.name) &&
    host.arguments.includes(consumed)
  );
};

export const noUnvalidatedJson = createRule({
  create: context => {
    const services = ESLintUtils.getParserServices(context);
    const checker = services.program.getTypeChecker();

    return {
      CallExpression: node => {
        const isJsonParse = isJsonParseCall(node);
        if (!isJsonParse) {
          if (!isJsonMethodCall(node)) return;
          const tsNode = services.esTreeNodeToTSNodeMap.get(node);
          const resultType = checker.getTypeAtLocation(tsNode);
          if (discriminateAnyType(resultType, checker, services.program, tsNode) === AnyType.Safe) return;
        }
        if (isZodParseConsumer(node)) return;
        context.report({
          data: { api: isJsonParse ? 'JSON.parse(…)' : '….json()' },
          messageId: 'validateJson',
          node,
        });
      },
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description:
        'Disallow consuming a deserialization boundary — `JSON.parse(…)` or a `.json()` call whose result is `any`/`Promise<any>` (a `Response`/`Bun.file` read) — without a zod schema. `JSON.parse` is matched syntactically (its signature always yields `any`); `.json()` is matched by type, so a domain `.json()` that already returns a typed value is left alone, while one returning `any`/`Promise<any>` is flagged whether or not it is awaited. The boundary value must flow directly (optionally through `await`) into a schema `.parse()`/`.safeParse()` — `Schema.parse(JSON.parse(text))`, `Schema.parse(await response.json())` — or through a helper that does, so the boundary returns a typed, runtime-checked value instead of an `as` cast or a hand-rolled `typeof`/`in` guard.',
      requiresTypeChecking: true,
    },
    messages: {
      validateJson:
        '`{{api}}` produces untyped `any` at a deserialization boundary. Validate it with a zod schema: pass the result directly to a schema `.parse()`/`.safeParse()` (`Schema.parse(JSON.parse(text))`, `Schema.parse(await response.json())`), or route it through a helper that does, so the boundary returns a typed, runtime-checked value instead of an `as` cast or a hand-rolled `typeof`/`in` guard.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'no-unvalidated-json',
});
