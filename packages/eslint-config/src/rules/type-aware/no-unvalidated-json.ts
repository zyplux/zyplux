import type { TSESTree } from '@typescript-eslint/utils';

import { AnyType, discriminateAnyType } from '@typescript-eslint/type-utils';
import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';
import { createNodeSchemaCheck } from '#rule-support/schema-checks';
import { createZodCallName } from '#rule-support/zod-calls';

const zodCheckMethods = new Set<string>([
  'parse',
  'parseAsync',
  'safeParse',
  'safeParseAsync',
  'validate',
  'validateAsync',
]);

const isJsonParseCall = ({ callee }: TSESTree.CallExpression) =>
  callee.type === AST_NODE_TYPES.MemberExpression &&
  !callee.computed &&
  callee.object.type === AST_NODE_TYPES.Identifier &&
  callee.object.name === 'JSON' &&
  callee.property.type === AST_NODE_TYPES.Identifier &&
  callee.property.name === 'parse';

const isJsonMethodCall = ({ callee }: TSESTree.CallExpression) =>
  callee.type === AST_NODE_TYPES.MemberExpression &&
  !callee.computed &&
  callee.property.type === AST_NODE_TYPES.Identifier &&
  callee.property.name === 'json';

export const noUnvalidatedJson = createRule({
  create: context => {
    const services = ESLintUtils.getParserServices(context);
    const checker = services.program.getTypeChecker();
    const isSchema = createNodeSchemaCheck(services);
    const getCallName = createZodCallName(services);
    const isSchemaConsumer = (source: TSESTree.CallExpression) => {
      const consumed = source.parent.type === AST_NODE_TYPES.AwaitExpression ? source.parent : source;
      const { parent: host } = consumed;
      if (host.type !== AST_NODE_TYPES.CallExpression || !zodCheckMethods.has(getCallName(host) ?? '')) return false;
      if (host.callee.type === AST_NODE_TYPES.MemberExpression && isSchema(host.callee.object))
        return host.arguments[0] === consumed;
      const [schema, input] = host.arguments;
      return schema !== undefined && isSchema(schema) && input === consumed;
    };

    return {
      CallExpression: node => {
        const isJsonParse = isJsonParseCall(node);
        if (!isJsonParse && !isJsonMethodCall(node)) return;
        const tsNode = services.esTreeNodeToTSNodeMap.get(node);
        const resultType = checker.getTypeAtLocation(tsNode);
        const boundaryType = discriminateAnyType(resultType, checker, services.program, tsNode);
        if (!isJsonParse && boundaryType === AnyType.Safe) return;
        const isResolved = boundaryType !== AnyType.PromiseAny || node.parent.type === AST_NODE_TYPES.AwaitExpression;
        if (isResolved && isSchemaConsumer(node)) return;
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
        'Require deserialized JSON to flow directly into schema parsing or boolean validation, with await required for JSON promises. JSON.parse is matched syntactically; .json() is matched when its return type is any or Promise<any>. Already typed .json() methods are permitted.',
      requiresTypeChecking: true,
    },
    messages: {
      validateJson:
        '`{{api}}` produces untyped `any`. Pass it directly to schema parsing or boolean validation, such as Schema.parse(JSON.parse(text)) or Schema.validate(await response.json()).',
    },
    schema: [],
    type: 'problem',
  },
  name: 'no-unvalidated-json',
});
