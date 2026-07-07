import type { TSESTree } from '@typescript-eslint/utils';

import { getConstrainedTypeAtLocation, isTypeArrayTypeOrUnionOfArrayTypes } from '@typescript-eslint/type-utils';
import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

const lengthReturningMethods = new Set<string>(['push', 'unshift']);

const passthroughParents = new Set<TSESTree.Node['type']>([
  AST_NODE_TYPES.ChainExpression,
  AST_NODE_TYPES.TSAsExpression,
  AST_NODE_TYPES.TSNonNullExpression,
  AST_NODE_TYPES.TSSatisfiesExpression,
  AST_NODE_TYPES.TSTypeAssertion,
]);

const statementGluingChars = new Set<string>(['(', '*', '+', ',', '-', '.', '/', '[', '`']);

const outermostResult = (call: TSESTree.CallExpression) => {
  let node: TSESTree.Node = call;
  while (passthroughParents.has(node.parent.type) && 'expression' in node.parent && node.parent.expression === node) {
    node = node.parent;
  }
  return node;
};

const isDiscarded = (call: TSESTree.CallExpression) => outermostResult(call).parent.type === AST_NODE_TYPES.ExpressionStatement;

const directReturnOf = (call: TSESTree.CallExpression) => {
  const parent = call.parent;
  if (parent.type === AST_NODE_TYPES.ReturnStatement && parent.argument === call) return parent;
  return;
};

export const noReturnArrayPush = createRule({
  create: context => {
    const services = ESLintUtils.getParserServices(context);
    const checker = services.program.getTypeChecker();

    return {
      CallExpression: node => {
        const callee = node.callee;
        if (callee.type !== AST_NODE_TYPES.MemberExpression || callee.computed) return;
        if (callee.property.type !== AST_NODE_TYPES.Identifier || !lengthReturningMethods.has(callee.property.name)) {
          return;
        }
        if (node.arguments.length === 0 || isDiscarded(node)) return;

        const receiverType = getConstrainedTypeAtLocation(services, callee.object);
        if (!isTypeArrayTypeOrUnionOfArrayTypes(receiverType, checker)) return;

        const method = callee.property.name;
        const returnStatement = directReturnOf(node);
        const blockReturn = returnStatement?.parent.type === AST_NODE_TYPES.BlockStatement ? returnStatement : undefined;

        context.report({
          data: { method },
          messageId: 'noReturnArrayPush',
          node: callee.property,
          ...(blockReturn && {
            suggest: [
              {
                data: { method },
                fix: fixer => {
                  const callText = context.sourceCode.getText(node);
                  const prefix = statementGluingChars.has(callText.at(0) ?? '') ? ';' : '';
                  return fixer.replaceText(blockReturn, `${prefix}${callText}; return;`);
                },
                messageId: 'separateReturn',
              },
            ],
          }),
        });
      },
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description:
        'Disallow using the return value of `Array#push()`/`Array#unshift()` — they return the new length, not the array or element. A type-aware replacement for `unicorn/no-return-array-push`: it inspects the receiver type, so domain methods named `push`/`unshift` (e.g. a git `push` that returns a promise) are left alone.',
      requiresTypeChecking: true,
    },
    hasSuggestions: true,
    messages: {
      noReturnArrayPush:
        'Do not use the return value of `Array#{{method}}(…)`; it is the new length, not the array or the inserted element. Call `{{method}}()` as its own statement.',
      separateReturn: 'Separate the `{{method}}()` call from `return`.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'no-return-array-push',
});
