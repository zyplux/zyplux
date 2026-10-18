import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';
import ts from 'typescript';

import { createRule } from '#create-rule';
import { collectScopeTree } from '#rule-support/scope-tree';
import { createZodCallName, createZodTypeCheck } from '#rule-support/zod-calls';

const isWithinRange = (container: TSESTree.Node, child: TSESTree.Node) =>
  container.range[0] <= child.range[0] && child.range[1] <= container.range[1];

export const noFunctionScopedSchema = createRule({
  create: context => {
    const services = ESLintUtils.getParserServices(context);
    const isSchema = (node: TSESTree.Node) => services.getTypeAtLocation(node).getProperty('_zod') !== undefined;
    const getCallName = createZodCallName(services);
    const isZodType = createZodTypeCheck(services);
    const checker = services.program.getTypeChecker();
    const isStableBinding = (identifier: TSESTree.Identifier | TSESTree.JSXIdentifier) => {
      const symbol = checker.getSymbolAtLocation(services.esTreeNodeToTSNodeMap.get(identifier));
      if (symbol === undefined) return false;
      const binding = symbol.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(symbol) : symbol;
      const type = services.getTypeAtLocation(identifier);
      const isZod = isZodType(type);
      return (binding.getDeclarations() ?? []).some(declaration => {
        if (ts.isSourceFile(declaration) || ts.isFunctionDeclaration(declaration)) return isZod;
        if (!ts.isVariableDeclaration(declaration) || !(declaration.parent.flags & ts.NodeFlags.Const)) return false;
        return (
          isZod ||
          (type.isUnion() ? type.types : [type]).every(
            member =>
              (member.flags &
                (ts.TypeFlags.StringLike |
                  ts.TypeFlags.NumberLike |
                  ts.TypeFlags.BooleanLike |
                  ts.TypeFlags.BigIntLike |
                  ts.TypeFlags.ESSymbolLike |
                  ts.TypeFlags.Null |
                  ts.TypeFlags.Undefined)) !==
              0,
          )
        );
      });
    };
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

    const getReceiverScope = (node: TSESTree.Node) => {
      let scope = context.sourceCode.getScope(node).variableScope;
      while (scope.block.type === AST_NODE_TYPES.ArrowFunctionExpression && scope.upper !== null)
        scope = scope.upper.variableScope;
      return scope;
    };

    const hasImmediateEffect = (node: TSESTree.CallExpression) => {
      const scope = context.sourceCode.getScope(node).variableScope;
      return [...effects, ...calls].some(
        effect =>
          isWithinRange(node, effect) &&
          (([AST_NODE_TYPES.MetaProperty, AST_NODE_TYPES.Super, AST_NODE_TYPES.ThisExpression].includes(effect.type) &&
            getReceiverScope(effect) === getReceiverScope(node)) ||
            (context.sourceCode.getScope(effect).variableScope === scope &&
              (effect.type !== AST_NODE_TYPES.CallExpression ||
                !isSchema(effect) ||
                getCallName(effect) === undefined ||
                ['describe', 'meta', 'register'].includes(getCallName(effect) ?? '')))),
      );
    };

    return {
      CallExpression: node => {
        calls.push(node);
      },
      'NewExpression, ThisExpression, Super, MetaProperty': (node: TSESTree.Node) => {
        effects.push(node);
      },
      'Program:exit': () => {
        for (const node of calls) {
          if (!isSchema(node) || getCallName(node) === undefined) continue;
          const fn = findFunction(node);
          if (
            fn === undefined ||
            isDeferredSchema(fn) ||
            references.some(
              ({ identifier, resolved }) =>
                isWithinRange(node, identifier) &&
                (resolved === null ||
                  (resolved.defs.every(definition => !isWithinRange(node, definition.name)) &&
                    (!['global', 'module'].includes(resolved.scope.type) || !isStableBinding(identifier)))),
            ) ||
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
