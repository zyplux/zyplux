import type { TSESLint, TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';
import { collectScopeTree } from '#rule-support/scope-tree';
import { createZodCallName } from '#rule-support/zod-calls';

const isWithinRange = (container: TSESTree.Node, child: TSESTree.Node) =>
  container.range[0] <= child.range[0] && child.range[1] <= container.range[1];

const hasLocalDependency = (node: TSESTree.Node, { identifier, resolved }: TSESLint.Scope.Reference) =>
  resolved !== null &&
  isWithinRange(node, identifier) &&
  resolved.defs.every(definition => !isWithinRange(node, definition.name)) &&
  (!['global', 'module'].includes(resolved.scope.type) ||
    resolved.defs.some(({ parent }) => parent?.type === AST_NODE_TYPES.VariableDeclaration && parent.kind !== 'const'));

export const noFunctionScopedSchema = createRule({
  create: context => {
    const services = ESLintUtils.getParserServices(context);
    const isSchema = (node: TSESTree.Node) => services.getTypeAtLocation(node).getProperty('_zod') !== undefined;
    const getCallName = createZodCallName(services);
    const calls: TSESTree.CallExpression[] = [];
    const effects: TSESTree.Node[] = [];
    const references = collectScopeTree(context.sourceCode.getScope(context.sourceCode.ast)).flatMap(
      scope => scope.references,
    );

    const findFunction = ({ parent }: TSESTree.Node) => {
      let ancestor = parent;
      while (ancestor !== undefined && ancestor.type !== AST_NODE_TYPES.Program) {
        if (
          [
            AST_NODE_TYPES.ArrowFunctionExpression,
            AST_NODE_TYPES.FunctionDeclaration,
            AST_NODE_TYPES.FunctionExpression,
          ].includes(ancestor.type)
        )
          return ancestor;
        if (
          ancestor.type === AST_NODE_TYPES.CallExpression &&
          isSchema(ancestor) &&
          getCallName(ancestor) !== undefined
        )
          return;
        ancestor = ancestor.parent;
      }
      return;
    };

    const isDeferredSchema = ({ parent }: TSESTree.Node) => {
      if (parent?.type === AST_NODE_TYPES.CallExpression) return getCallName(parent) === 'lazy';
      if (parent?.type !== AST_NODE_TYPES.Property || parent.kind !== 'get') return false;
      const owner = parent.parent.parent;
      return owner.type === AST_NODE_TYPES.CallExpression && getCallName(owner) !== undefined && isSchema(owner);
    };

    const hasImmediateEffect = (node: TSESTree.CallExpression) => {
      const scope = context.sourceCode.getScope(node).variableScope;
      return [...effects, ...calls].some(
        effect =>
          isWithinRange(node, effect) &&
          context.sourceCode.getScope(effect).variableScope === scope &&
          (effect.type !== AST_NODE_TYPES.CallExpression || getCallName(effect) === undefined),
      );
    };

    return {
      CallExpression: node => {
        calls.push(node);
      },
      'NewExpression, ThisExpression': (node: TSESTree.Node) => {
        effects.push(node);
      },
      'Program:exit': () => {
        for (const node of calls) {
          if (!isSchema(node) || getCallName(node) === undefined) continue;
          const fn = findFunction(node);
          if (
            fn === undefined ||
            isDeferredSchema(fn) ||
            references.some(reference => hasLocalDependency(node, reference)) ||
            hasImmediateEffect(node)
          )
            continue;
          context.report({ messageId: 'hoistSchema', node });
        }
      },
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description:
        'Declare reusable Zod schemas outside functions; permit factories depending on local inputs and deferred recursive schemas.',
      requiresTypeChecking: true,
    },
    messages: { hoistSchema: 'Construct this schema once outside the function so calls reuse the same instance.' },
    schema: [],
    type: 'suggestion',
  },
  name: 'no-function-scoped-schema',
});
