import type { TSESLint, TSESTree } from '@typescript-eslint/utils';

import { isTypeAnyType } from '@typescript-eslint/type-utils';
import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

type AliasAbsorption = {
  declaration: TSESTree.VariableDeclaration;
  local: TSESTree.Identifier;
  localVariable: TSESLint.Scope.Variable;
  property: string;
};

type DestructurePlan = {
  aliasAbsorptions: AliasAbsorption[];
  directReads: PropertyRead[];
  localCollisions: string[];
  param: TSESTree.Identifier;
  propertyNames: string[];
};

type FunctionNode = TSESTree.ArrowFunctionExpression | TSESTree.FunctionDeclaration | TSESTree.FunctionExpression;

type PropertyRead = {
  member: TSESTree.MemberExpression;
  property: string;
};

const reservedBindingNames = new Set<string>([
  'arguments',
  'await',
  'break',
  'case',
  'catch',
  'class',
  'const',
  'continue',
  'debugger',
  'default',
  'delete',
  'do',
  'else',
  'enum',
  'eval',
  'export',
  'extends',
  'false',
  'finally',
  'for',
  'function',
  'if',
  'implements',
  'import',
  'in',
  'instanceof',
  'interface',
  'let',
  'new',
  'null',
  'package',
  'private',
  'protected',
  'public',
  'return',
  'static',
  'super',
  'switch',
  'this',
  'throw',
  'true',
  'try',
  'typeof',
  'var',
  'void',
  'while',
  'with',
  'yield',
]);

const isPlainPropertyRead = (member: TSESTree.MemberExpression) => {
  const parent = member.parent;
  const isCallee =
    (parent.type === AST_NODE_TYPES.CallExpression || parent.type === AST_NODE_TYPES.NewExpression) &&
    parent.callee === member;
  const isTaggedTemplate = parent.type === AST_NODE_TYPES.TaggedTemplateExpression && parent.tag === member;
  const isAssignmentTarget = parent.type === AST_NODE_TYPES.AssignmentExpression && parent.left === member;
  const isUpdateTarget = parent.type === AST_NODE_TYPES.UpdateExpression;
  const isDeleteTarget = parent.type === AST_NODE_TYPES.UnaryExpression && parent.operator === 'delete';
  const isLoopTarget =
    (parent.type === AST_NODE_TYPES.ForInStatement || parent.type === AST_NODE_TYPES.ForOfStatement) &&
    parent.left === member;
  return !(isCallee || isTaggedTemplate || isAssignmentTarget || isUpdateTarget || isDeleteTarget || isLoopTarget);
};

const propertyReadOf = (identifier: TSESTree.Node) => {
  const member = identifier.parent;
  if (member?.type !== AST_NODE_TYPES.MemberExpression) return;
  if (
    member.object !== identifier ||
    member.computed ||
    member.optional ||
    member.property.type !== AST_NODE_TYPES.Identifier ||
    reservedBindingNames.has(member.property.name) ||
    !isPlainPropertyRead(member)
  ) {
    return;
  }
  return { member, property: member.property.name };
};

const collectScopeTree = (root: TSESLint.Scope.Scope) => {
  const scopes: TSESLint.Scope.Scope[] = [];
  const pending = [root];
  while (pending.length > 0) {
    const scope = pending.pop();
    if (!scope) continue;
    scopes.push(scope);
    pending.push(...scope.childScopes);
  }
  return scopes;
};

const collectSortedReads = ({ references }: TSESLint.Scope.Variable) => {
  const reads: PropertyRead[] = [];
  for (const reference of references) {
    const read = propertyReadOf(reference.identifier);
    if (!read) return;
    reads.push(read);
  }
  return reads.toSorted((left, right) => left.member.range[0] - right.member.range[0]);
};

const constAliasOf = (member: TSESTree.MemberExpression) => {
  const declarator = member.parent;
  if (
    declarator.type !== AST_NODE_TYPES.VariableDeclarator ||
    declarator.init !== member ||
    declarator.id.type !== AST_NODE_TYPES.Identifier ||
    declarator.parent.kind !== 'const' ||
    declarator.parent.declarations.length !== 1
  ) {
    return;
  }
  return { declaration: declarator.parent, local: declarator.id };
};

const partitionReads = (sourceCode: Readonly<TSESLint.SourceCode>, reads: readonly PropertyRead[]) => {
  const aliasAbsorptions: AliasAbsorption[] = [];
  const directReads: PropertyRead[] = [];
  const propertyNames: string[] = [];
  const seenProperties = new Set<string>();

  for (const read of reads) {
    if (!seenProperties.has(read.property)) {
      seenProperties.add(read.property);
      propertyNames.push(read.property);
    }

    const alias = constAliasOf(read.member);
    if (!alias) {
      directReads.push(read);
      continue;
    }
    const localVariable = sourceCode
      .getDeclaredVariables(alias.declaration)
      .find(variable => variable.defs.some(def => def.name === alias.local));
    if (!localVariable) return;
    aliasAbsorptions.push({ ...alias, localVariable, property: read.property });
  }

  return { aliasAbsorptions, directReads, propertyNames };
};

const hasAliasRenameConflict = (aliasAbsorptions: readonly AliasAbsorption[]) => {
  const removedNames = new Set(aliasAbsorptions.map(absorption => absorption.local.name));
  return aliasAbsorptions.some(
    absorption => absorption.local.name !== absorption.property && removedNames.has(absorption.property),
  );
};

const hasFreeVariableCapture = ({ through }: TSESLint.Scope.Scope, introducedNames: ReadonlySet<string>) =>
  through.some(reference => introducedNames.has(reference.identifier.name));

const findLocalCollisions = (
  functionScope: TSESLint.Scope.Scope,
  introducedNames: ReadonlySet<string>,
  exemptVariables: ReadonlySet<TSESLint.Scope.Variable>,
) => {
  const collidingLocals = new Set<string>();
  const scopedVariables = collectScopeTree(functionScope).flatMap(scope => scope.variables);
  for (const variable of scopedVariables) {
    if (exemptVariables.has(variable)) continue;
    if (introducedNames.has(variable.name)) collidingLocals.add(variable.name);
  }
  return [...collidingLocals].toSorted((left, right) => left.localeCompare(right));
};

const wholeLineRemovalSpan = ({ text }: Readonly<TSESLint.SourceCode>, { range }: TSESTree.Node) => {
  let start = range[0];
  while (start > 0 && (text[start - 1] === ' ' || text[start - 1] === '\t')) {
    start--;
  }
  const isOwnLine = start === 0 || text[start - 1] === '\n' || text[start - 1] === '\r';
  if (!isOwnLine) return { end: range[1], start: range[0] };

  let end = range[1];
  while (end < text.length && (text[end] === ' ' || text[end] === '\t')) {
    end++;
  }
  if (text[end] === '\r') end++;
  if (text[end] === '\n') end++;
  return { end, start };
};

export const preferDestructuredParams = createRule({
  create: context => {
    const { sourceCode } = context;
    const services = ESLintUtils.getParserServices(context);
    const checker = services.program.getTypeChecker();

    const bindsDeclaredProperties = (param: TSESTree.Identifier, propertyNames: readonly string[]) => {
      const paramType = services.getTypeAtLocation(param);
      if (isTypeAnyType(paramType)) return true;
      return propertyNames.every(name => checker.getPropertyOfType(paramType, name) !== undefined);
    };

    const planParameter = (param: TSESTree.Parameter, declaredVariables: readonly TSESLint.Scope.Variable[]) => {
      // Annotated params only — drop the `!param.typeAnnotation` check to also flag inferred-type params (e.g. inline callbacks).
      if (param.type !== AST_NODE_TYPES.Identifier || param.optional || !param.typeAnnotation) return;

      const paramVariable = declaredVariables.find(variable => variable.defs.some(def => def.name === param));
      if (!paramVariable || paramVariable.references.length === 0) return;

      const reads = collectSortedReads(paramVariable);
      if (!reads) return;

      const partition = partitionReads(sourceCode, reads);
      if (!partition) return;
      const { aliasAbsorptions, directReads, propertyNames } = partition;
      if (hasAliasRenameConflict(aliasAbsorptions)) return;
      if (!bindsDeclaredProperties(param, propertyNames)) return;

      const introducedNames = new Set(propertyNames);
      const functionScope = paramVariable.scope;
      if (hasFreeVariableCapture(functionScope, introducedNames)) return;

      const exemptVariables = new Set([paramVariable, ...aliasAbsorptions.map(absorption => absorption.localVariable)]);
      const localCollisions = findLocalCollisions(functionScope, introducedNames, exemptVariables);
      return { aliasAbsorptions, directReads, localCollisions, param, propertyNames };
    };

    const reportPlan = ({ aliasAbsorptions, directReads, localCollisions, param, propertyNames }: DestructurePlan) => {
      if (localCollisions.length > 0) {
        context.report({
          data: { collisions: localCollisions.join(', '), name: param.name, properties: propertyNames.join(', ') },
          messageId: 'destructureParameterNoFix',
          node: param,
        });
        return;
      }

      const pattern = `{ ${propertyNames.join(', ')} }`;
      const nameRange: TSESLint.AST.Range = [param.range[0], param.range[0] + param.name.length];

      context.report({
        data: { name: param.name, properties: propertyNames.join(', ') },
        fix: fixer => {
          const fixes = [fixer.replaceTextRange(nameRange, pattern)];
          for (const absorption of aliasAbsorptions) {
            const { end, start } = wholeLineRemovalSpan(sourceCode, absorption.declaration);
            fixes.push(fixer.removeRange([start, end]));
            if (absorption.local.name !== absorption.property) {
              for (const reference of absorption.localVariable.references) {
                if (reference.identifier !== absorption.local) {
                  fixes.push(fixer.replaceText(reference.identifier, absorption.property));
                }
              }
            }
          }
          for (const directRead of directReads) {
            fixes.push(fixer.replaceText(directRead.member, directRead.property));
          }
          return fixes;
        },
        messageId: 'destructureParameter',
        node: param,
      });
    };

    const checkFunction = (node: FunctionNode) => {
      const declaredVariables = sourceCode.getDeclaredVariables(node);

      const plans: DestructurePlan[] = [];
      for (const param of node.params) {
        const plan = planParameter(param, declaredVariables);
        if (plan) plans.push(plan);
      }
      if (plans.length === 0) return;

      const introductionCounts = new Map<string, number>();
      for (const plan of plans) {
        for (const name of plan.propertyNames) {
          introductionCounts.set(name, (introductionCounts.get(name) ?? 0) + 1);
        }
      }

      for (const plan of plans) {
        if (plan.propertyNames.some(name => (introductionCounts.get(name) ?? 0) > 1)) continue;
        reportPlan(plan);
      }
    };

    return {
      ArrowFunctionExpression: checkFunction,
      FunctionDeclaration: checkFunction,
      FunctionExpression: checkFunction,
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description:
        'Require destructuring an explicitly-typed function parameter that is never used as a whole — only its properties are read. The accessed properties are pulled into the parameter pattern (`{ a, b }: T`) and the body is rewritten, with an autofix that also absorbs `const` aliases (`const parent = node.parent`). Accesses that call (`p.fn()`), write (`p.x = …`), increment, `delete`, index (`p[k]`), or optionally chain (`p?.x`) keep the whole object, so the parameter is left alone; parameters without a type annotation (e.g. inferred inline callbacks) are also left alone. A property that the parameter’s declared type does not carry — readable only after narrowing, as in `node.type === X && node.declare` on a union — exempts the parameter, since the destructured pattern could not typecheck. When a property name would collide with a binding declared inside the function, the parameter is still reported but no autofix is offered (rename the local first); when it would instead capture a free variable the body reads from an outer scope, the parameter is left alone entirely.',
      requiresTypeChecking: true,
    },
    fixable: 'code',
    messages: {
      destructureParameter:
        'Parameter `{{name}}` is only used to read its properties ({{properties}}); destructure them in the parameter list instead of taking the whole object.',
      destructureParameterNoFix:
        'Parameter `{{name}}` is only used to read its properties ({{properties}}); destructure them in the parameter list instead of taking the whole object. No autofix: the binding name(s) {{collisions}} already name a local declaration — rename those first.',
    },
    schema: [],
    type: 'suggestion',
  },
  name: 'prefer-destructured-params',
});
