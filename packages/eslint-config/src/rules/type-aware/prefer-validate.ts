import type { TSESLint, TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';
import ts from 'typescript';

import { createRule } from '#create-rule';
import { createZodCallName } from '#rule-support/zod-calls';

const parseMethods = new Map([
  ['safeParse', 'validate'],
  ['safeParseAsync', 'validateAsync'],
  ['spa', 'validateAsync'],
]);

const isSuccessPattern = (node: TSESTree.Node) => {
  if (node.type !== AST_NODE_TYPES.ObjectPattern || node.properties.length !== 1) return false;
  const [property] = node.properties;
  return (
    property?.type === AST_NODE_TYPES.Property &&
    !property.computed &&
    property.key.type === AST_NODE_TYPES.Identifier &&
    property.key.name === 'success' &&
    property.value.type === AST_NODE_TYPES.Identifier
  );
};

const isSuccessRead = (identifier: TSESTree.Node) => {
  const member = identifier.parent;
  return (
    member?.type === AST_NODE_TYPES.MemberExpression &&
    member.object === identifier &&
    !member.computed &&
    member.property.type === AST_NODE_TYPES.Identifier &&
    member.property.name === 'success' &&
    !(member.parent.type === AST_NODE_TYPES.AssignmentExpression && member.parent.left === member) &&
    member.parent.type !== AST_NODE_TYPES.UpdateExpression &&
    !(member.parent.type === AST_NODE_TYPES.UnaryExpression && member.parent.operator === 'delete')
  );
};

const hasOnlySuccessReads = ({ references }: TSESLint.Scope.Variable) => {
  const reads = references.filter(reference => reference.isRead());
  return (
    reads.length > 0 &&
    references.every(reference => !reference.isWrite() || reference.init === true) &&
    reads.every(reference => isSuccessRead(reference.identifier))
  );
};

export const preferValidate = createRule({
  create: context => {
    const services = ESLintUtils.getParserServices(context);
    const getCallName = createZodCallName(services);
    const checker = services.program.getTypeChecker();
    const hasValidation = (callee: TSESTree.CallExpression['callee'], method: string) => {
      if (callee.type === AST_NODE_TYPES.MemberExpression)
        return services.getTypeAtLocation(callee.object).getProperty(method) !== undefined;
      const symbol = checker.getSymbolAtLocation(services.esTreeNodeToTSNodeMap.get(callee));
      if (symbol === undefined) return false;
      const binding = symbol.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(symbol) : symbol;
      const declaration = binding.getDeclarations()?.[0];
      const module = declaration && checker.getSymbolAtLocation(declaration.getSourceFile());
      return module !== undefined && checker.getExportsOfModule(module).some(member => member.getName() === method);
    };
    return {
      CallExpression: node => {
        const method = parseMethods.get(getCallName(node) ?? '');
        if (method === undefined || !hasValidation(node.callee, method)) return;
        const parsed = node.parent.type === AST_NODE_TYPES.AwaitExpression ? node.parent : node;
        if (method === 'validateAsync' && parsed === node) return;
        const declaration = parsed.parent;
        const isSuccessOnly =
          isSuccessRead(parsed) ||
          (declaration.type === AST_NODE_TYPES.VariableDeclarator &&
            (isSuccessPattern(declaration.id) ||
              (declaration.id.type === AST_NODE_TYPES.Identifier &&
                declaration.parent.parent.type !== AST_NODE_TYPES.ExportNamedDeclaration &&
                context.sourceCode.getDeclaredVariables(declaration).some(variable => hasOnlySuccessReads(variable)))));
        if (isSuccessOnly) context.report({ data: { method }, messageId: 'preferValidate', node });
      },
    };
  },
  meta: {
    docs: {
      description:
        'Use Zod boolean validation when a parse result is consumed only through success, including imported and parameter schemas.',
      requiresTypeChecking: true,
    },
    messages: {
      preferValidate: 'Use {{method}}() when only parse success is needed; keep parsing for data or error details.',
    },
    schema: [],
    type: 'suggestion',
  },
  name: 'prefer-validate',
});
