import type { TSESLint, TSESTree } from '@typescript-eslint/utils';

import { isTypeAnyType, isTypeUnknownType } from '@typescript-eslint/type-utils';
import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';
import * as ts from 'typescript';

import { createRule } from '#create-rule';

type FunctionNode = TSESTree.ArrowFunctionExpression | TSESTree.FunctionDeclaration | TSESTree.FunctionExpression;

type MessageId =
  'narrowReturnType' | 'narrowVarType' | 'removeAnnotation' | 'removeParamType' | 'removeReturnType' | 'removeVarType';

type NoTypeAnnotationsOptions = [{ narrowing: boolean; redundant: boolean }];

const ignoredKeys = new Set<string>(['loc', 'parent', 'range']);

const childNodes = (node: object) => {
  const children: object[] = [];
  for (const [key, value] of Object.entries(node)) {
    if (ignoredKeys.has(key)) continue;
    const items: unknown[] = Array.isArray(value) ? value : [value];
    for (const item of items) {
      if (item !== null && typeof item === 'object') children.push(item);
    }
  }
  return children;
};

const hasMatchingNode = (node: object, isMatch: (n: object) => boolean): boolean =>
  isMatch(node) || childNodes(node).some(child => hasMatchingNode(child, isMatch));

const isIdentifierNamed = (node: object, isWanted: (name: string) => boolean) =>
  'type' in node &&
  node.type === AST_NODE_TYPES.Identifier &&
  'name' in node &&
  typeof node.name === 'string' &&
  isWanted(node.name);

const getFunctionName = (fn: FunctionNode) => {
  if ('id' in fn && fn.id) return fn.id.name;
  const { parent } = fn;
  if (parent.type === AST_NODE_TYPES.VariableDeclarator && parent.id.type === AST_NODE_TYPES.Identifier) {
    return parent.id.name;
  }
  if ('key' in parent && 'computed' in parent && !parent.computed && parent.key.type === AST_NODE_TYPES.Identifier) {
    return parent.key.name;
  }
  return;
};

const isRecursiveFunction = (fn: FunctionNode) => {
  const name = getFunctionName(fn);
  return name !== undefined && hasMatchingNode(fn.body, n => isIdentifierNamed(n, candidate => candidate === name));
};

const collectTypeParamNames = (declaration: TSESTree.TSTypeParameterDeclaration | undefined) => {
  const names = new Set<string>();
  const params = declaration?.params ?? [];
  for (const param of params) {
    names.add(param.name.name);
  }
  return names;
};

const hasTypeParamReference = (typeNode: TSESTree.TypeNode, typeParamNames: ReadonlySet<string>) =>
  hasMatchingNode(
    typeNode,
    n =>
      'type' in n &&
      n.type === AST_NODE_TYPES.TSTypeReference &&
      'typeName' in n &&
      typeof n.typeName === 'object' &&
      n.typeName !== null &&
      isIdentifierNamed(n.typeName, name => typeParamNames.has(name)),
  );

const declarationContainers = new Set<TSESTree.Node['type']>([
  AST_NODE_TYPES.AccessorProperty,
  AST_NODE_TYPES.ArrayExpression,
  AST_NODE_TYPES.ClassBody,
  AST_NODE_TYPES.ClassDeclaration,
  AST_NODE_TYPES.ClassExpression,
  AST_NODE_TYPES.MethodDefinition,
  AST_NODE_TYPES.ObjectExpression,
  AST_NODE_TYPES.Property,
  AST_NODE_TYPES.PropertyDefinition,
  AST_NODE_TYPES.VariableDeclaration,
  AST_NODE_TYPES.VariableDeclarator,
]);

const hasExportedAncestor = ({ parent }: TSESTree.Node): boolean => {
  if (!parent) return false;
  if (
    parent.type === AST_NODE_TYPES.ExportNamedDeclaration ||
    parent.type === AST_NODE_TYPES.ExportDefaultDeclaration
  ) {
    return true;
  }
  return declarationContainers.has(parent.type) && hasExportedAncestor(parent);
};

const isTopLevel = ({ parent }: TSESTree.Node) => parent?.type === AST_NODE_TYPES.Program;

const isArrowAtModuleBoundary = (arrow: TSESTree.ArrowFunctionExpression, exportedNames: ReadonlySet<string>) => {
  if (hasExportedAncestor(arrow)) return true;
  const { parent } = arrow;
  return (
    parent.type === AST_NODE_TYPES.VariableDeclarator &&
    parent.id.type === AST_NODE_TYPES.Identifier &&
    isTopLevel(parent.parent) &&
    exportedNames.has(parent.id.name)
  );
};

const isDeclaratorAtModuleBoundary = (declarator: TSESTree.VariableDeclarator, exportedNames: ReadonlySet<string>) => {
  if (hasExportedAncestor(declarator)) return true;
  return (
    declarator.id.type === AST_NODE_TYPES.Identifier &&
    isTopLevel(declarator.parent) &&
    exportedNames.has(declarator.id.name)
  );
};

const collectExportedNames = ({ body }: TSESTree.Program) => {
  const names = new Set<string>();
  for (const statement of body) {
    if (statement.type !== AST_NODE_TYPES.ExportNamedDeclaration || statement.source) continue;
    for (const specifier of statement.specifiers) {
      names.add(specifier.local.name);
    }
  }
  return names;
};

const selfDeterminedInitializers = new Set<TSESTree.Node['type']>([
  AST_NODE_TYPES.BinaryExpression,
  AST_NODE_TYPES.Identifier,
  AST_NODE_TYPES.MemberExpression,
  AST_NODE_TYPES.TemplateLiteral,
  AST_NODE_TYPES.UnaryExpression,
]);

const annotatedIdentifierParam = (param: TSESTree.Parameter) => {
  const binding = param.type === AST_NODE_TYPES.AssignmentPattern ? param.left : param;
  return binding.type === AST_NODE_TYPES.Identifier && binding.typeAnnotation ? binding : undefined;
};

const isInferableType = (type: ts.Type) => !isTypeAnyType(type) && !isTypeUnknownType(type);

const isSelfReferentialContextualParam = ({ valueDeclaration }: ts.Symbol, ownParameters: ReadonlySet<ts.Node>) =>
  valueDeclaration !== undefined && ownParameters.has(valueDeclaration);

const isNestedFunctionNode = (node: ts.Node) =>
  ts.isFunctionDeclaration(node) ||
  ts.isFunctionExpression(node) ||
  ts.isArrowFunction(node) ||
  ts.isMethodDeclaration(node) ||
  ts.isGetAccessorDeclaration(node) ||
  ts.isSetAccessorDeclaration(node) ||
  ts.isConstructorDeclaration(node);

const collectReturnExpressions = (node: ts.Node, found: ts.Expression[]) => {
  node.forEachChild(child => {
    if (isNestedFunctionNode(child)) return;
    if (ts.isReturnStatement(child) && child.expression) found.push(child.expression);
    collectReturnExpressions(child, found);
  });
};

const isCallableType = (type: ts.Type) =>
  type.getCallSignatures().length > 0 || type.getConstructSignatures().length > 0;

const isClosedShape = (annotationType: ts.Type) =>
  (annotationType.getProperties().length > 0 || isCallableType(annotationType)) && !annotationType.getStringIndexType();

const isNamedField = (member: ts.Symbol) => !member.getName().startsWith('__');

const findHiddenMembers = (annotationType: ts.Type, valueTypes: readonly ts.Type[]) => {
  const [first, ...rest] = valueTypes;
  if (!first) return [];
  const hidden: string[] = [];
  for (const member of first.getProperties()) {
    const name = member.getName();
    if (!isNamedField(member) || annotationType.getProperty(name)) continue;
    if (rest.every(valueType => valueType.getProperty(name))) hidden.push(name);
  }
  return hidden;
};

const isThisDotField = (node: object, fieldName: string) =>
  'type' in node &&
  node.type === AST_NODE_TYPES.MemberExpression &&
  'computed' in node &&
  node.computed === false &&
  'object' in node &&
  typeof node.object === 'object' &&
  node.object !== null &&
  'type' in node.object &&
  node.object.type === AST_NODE_TYPES.ThisExpression &&
  'property' in node &&
  typeof node.property === 'object' &&
  node.property !== null &&
  isIdentifierNamed(node.property, name => name === fieldName);

const isFieldWrite = (node: object, fieldName: string) =>
  'type' in node &&
  node.type === AST_NODE_TYPES.AssignmentExpression &&
  'left' in node &&
  typeof node.left === 'object' &&
  node.left !== null &&
  isThisDotField(node.left, fieldName);

const isReassignedField = ({ key, parent }: TSESTree.PropertyDefinition) => {
  if (key.type !== AST_NODE_TYPES.Identifier) return false;
  const fieldName = key.name;
  return hasMatchingNode(parent, node => isFieldWrite(node, fieldName));
};

type NarrowingReport = {
  annotationNode: TSESTree.TSTypeAnnotation;
  annotationType: ts.Type;
  fix: TSESLint.ReportFixFunction;
  messageId: 'narrowReturnType' | 'narrowVarType';
  valueTypes: readonly ts.Type[];
};

export const noTypeAnnotations = createRule<NoTypeAnnotationsOptions, MessageId>({
  create: (context, [{ narrowing, redundant }]) => {
    const services = ESLintUtils.getParserServices(context);
    const checker = services.program.getTypeChecker();
    let exportedNames: ReadonlySet<string> = new Set();

    const reportRedundant = (annotation: TSESTree.TSTypeAnnotation, messageId: 'removeParamType' | 'removeVarType') => {
      context.report({
        fix: fixer => fixer.removeRange(annotation.range),
        messageId,
        node: annotation,
      });
    };

    const checkRedundantArrowReturn = (arrow: TSESTree.ArrowFunctionExpression) => {
      const returnAnnotation = arrow.returnType;
      if (!returnAnnotation) return false;
      if (returnAnnotation.typeAnnotation.type === AST_NODE_TYPES.TSTypePredicate) return false;
      if (isArrowAtModuleBoundary(arrow, exportedNames)) return false;

      const typeParamNames = collectTypeParamNames(arrow.typeParameters);
      if (typeParamNames.size > 0 && hasTypeParamReference(returnAnnotation.typeAnnotation, typeParamNames)) {
        return false;
      }
      if (isRecursiveFunction(arrow)) return false;

      const tokenBefore = context.sourceCode.getTokenBefore(returnAnnotation);
      context.report({
        ...(tokenBefore && {
          fix: fixer => fixer.removeRange([tokenBefore.range[1], returnAnnotation.range[1]]),
        }),
        messageId: 'removeReturnType',
        node: returnAnnotation,
      });
      return true;
    };

    const isContextualParamInferredFromCallback = (arrow: TSESTree.ArrowFunctionExpression, paramIndex: number) => {
      const { parent } = arrow;
      if (parent.type !== AST_NODE_TYPES.CallExpression && parent.type !== AST_NODE_TYPES.NewExpression) return false;
      const isConstruct = parent.type === AST_NODE_TYPES.NewExpression;

      const argIndex = parent.arguments.indexOf(arrow);
      if (argIndex === -1) return false;

      const calleeType = services.getTypeAtLocation(parent.callee);
      const calleeSignatures = isConstruct ? calleeType.getConstructSignatures() : calleeType.getCallSignatures();

      return calleeSignatures.some(signature => {
        const typeParamsSet = new Set<ts.Type>(signature.typeParameters);
        if (typeParamsSet.size === 0) return false;

        const calleeParam = signature.parameters[argIndex];
        if (!calleeParam?.valueDeclaration) return false;

        const callbackType = checker.getTypeOfSymbolAtLocation(calleeParam, calleeParam.valueDeclaration);
        const callbackParam = callbackType.getCallSignatures()[0]?.parameters[paramIndex];
        if (!callbackParam?.valueDeclaration) return false;

        const callbackParamType = checker.getTypeOfSymbolAtLocation(callbackParam, callbackParam.valueDeclaration);
        return typeParamsSet.has(callbackParamType);
      });
    };

    const checkParams = (arrow: TSESTree.ArrowFunctionExpression) => {
      if (isArrowAtModuleBoundary(arrow, exportedNames)) return;

      const tsArrow = services.esTreeNodeToTSNodeMap.get(arrow);
      const contextualType = checker.getContextualType(tsArrow);
      if (!contextualType) return;

      const signatures = contextualType.getCallSignatures();
      if (signatures.length !== 1) return;
      const signature = signatures[0];
      if (!signature) return;

      const ownParameters = new Set<ts.Node>(tsArrow.parameters);

      for (const [index, param] of arrow.params.entries()) {
        const binding = annotatedIdentifierParam(param);
        if (!binding?.typeAnnotation) continue;

        const contextualParam = signature.parameters[index];
        if (!contextualParam) continue;
        if (isSelfReferentialContextualParam(contextualParam, ownParameters)) continue;
        if (isContextualParamInferredFromCallback(arrow, index)) continue;

        const contextualParamType = checker.getTypeOfSymbolAtLocation(contextualParam, tsArrow);
        const annotatedType = services.getTypeAtLocation(binding);
        if (annotatedType !== contextualParamType || !isInferableType(annotatedType)) continue;

        reportRedundant(binding.typeAnnotation, 'removeParamType');
      }
    };

    const checkRedundantInitializer = (
      annotatedNode: TSESTree.Node,
      annotation: TSESTree.TSTypeAnnotation | undefined,
      initializer: null | TSESTree.Expression,
    ) => {
      if (!annotation || !initializer || !selfDeterminedInitializers.has(initializer.type)) return false;
      if (initializer.type === AST_NODE_TYPES.Identifier && initializer.name === 'undefined') return false;

      const annotatedType = services.getTypeAtLocation(annotatedNode);
      const initializerType = services.getTypeAtLocation(initializer);
      if (annotatedType !== initializerType || !isInferableType(annotatedType)) return false;

      reportRedundant(annotation, 'removeVarType');
      return true;
    };

    const checkRedundantVariable = (declarator: TSESTree.VariableDeclarator) => {
      if (declarator.id.type !== AST_NODE_TYPES.Identifier) return false;
      if (isDeclaratorAtModuleBoundary(declarator, exportedNames)) return false;
      return checkRedundantInitializer(declarator.id, declarator.id.typeAnnotation, declarator.init);
    };

    const checkRedundantProperty = (property: TSESTree.PropertyDefinition) => {
      if (property.computed || property.key.type !== AST_NODE_TYPES.Identifier) return false;
      if (hasExportedAncestor(property)) return false;
      return checkRedundantInitializer(property.key, property.typeAnnotation, property.value);
    };

    const reportNarrowing = ({ annotationNode, annotationType, fix, messageId, valueTypes }: NarrowingReport) => {
      if (!isClosedShape(annotationType)) return;
      const hidden = findHiddenMembers(annotationType, valueTypes);
      if (hidden.length === 0) return;

      context.report({
        data: { members: hidden.join(', ') },
        messageId,
        node: annotationNode,
        suggest: [{ fix, messageId: 'removeAnnotation' }],
      });
    };

    const collectReturnedTypes = (fn: FunctionNode) => {
      const { body } = fn;
      if (body.type !== AST_NODE_TYPES.BlockStatement) return [services.getTypeAtLocation(body)];
      const expressions: ts.Expression[] = [];
      collectReturnExpressions(services.esTreeNodeToTSNodeMap.get(body), expressions);
      return expressions.map(expression => checker.getTypeAtLocation(expression));
    };

    const checkNarrowingReturn = (fn: FunctionNode) => {
      const returnAnnotation = fn.returnType;
      if (!returnAnnotation) return;
      if (returnAnnotation.typeAnnotation.type === AST_NODE_TYPES.TSTypePredicate) return;
      if (fn.async || ('generator' in fn && fn.generator)) return;

      const typeParamNames = collectTypeParamNames(fn.typeParameters);
      if (typeParamNames.size > 0 && hasTypeParamReference(returnAnnotation.typeAnnotation, typeParamNames)) return;
      if (isRecursiveFunction(fn)) return;

      const tokenBefore = context.sourceCode.getTokenBefore(returnAnnotation);
      if (!tokenBefore) return;

      const signature = checker.getSignatureFromDeclaration(services.esTreeNodeToTSNodeMap.get(fn));
      if (!signature) return;

      const valueTypes = collectReturnedTypes(fn);
      if (valueTypes.length === 0) return;

      reportNarrowing({
        annotationNode: returnAnnotation,
        annotationType: signature.getReturnType(),
        fix: fixer => fixer.removeRange([tokenBefore.range[1], returnAnnotation.range[1]]),
        messageId: 'narrowReturnType',
        valueTypes,
      });
    };

    const checkNarrowingVariable = (declarator: TSESTree.VariableDeclarator) => {
      if (declarator.id.type !== AST_NODE_TYPES.Identifier) return;
      const annotation = declarator.id.typeAnnotation;
      if (!annotation || !declarator.init) return;

      const [variable] = context.sourceCode.getDeclaredVariables(declarator);
      const wasReassigned =
        variable?.references.some(reference => reference.isWrite() && reference.identifier !== declarator.id) ?? false;
      if (wasReassigned) return;

      reportNarrowing({
        annotationNode: annotation,
        annotationType: services.getTypeAtLocation(declarator.id),
        fix: fixer => fixer.removeRange(annotation.range),
        messageId: 'narrowVarType',
        valueTypes: [services.getTypeAtLocation(declarator.init)],
      });
    };

    const checkNarrowingProperty = (property: TSESTree.PropertyDefinition) => {
      if (property.computed || property.key.type !== AST_NODE_TYPES.Identifier) return;
      const annotation = property.typeAnnotation;
      if (!annotation || !property.value) return;
      if (isReassignedField(property)) return;

      reportNarrowing({
        annotationNode: annotation,
        annotationType: services.getTypeAtLocation(property.key),
        fix: fixer => fixer.removeRange(annotation.range),
        messageId: 'narrowVarType',
        valueTypes: [services.getTypeAtLocation(property.value)],
      });
    };

    return {
      ArrowFunctionExpression: arrow => {
        const didReportReturn = redundant ? checkRedundantArrowReturn(arrow) : false;
        if (redundant) checkParams(arrow);
        if (narrowing && !didReportReturn) checkNarrowingReturn(arrow);
      },
      FunctionDeclaration: fn => {
        if (narrowing) checkNarrowingReturn(fn);
      },
      FunctionExpression: fn => {
        if (narrowing) checkNarrowingReturn(fn);
      },
      Program: program => {
        exportedNames = collectExportedNames(program);
      },
      PropertyDefinition: property => {
        const didReport = redundant ? checkRedundantProperty(property) : false;
        if (narrowing && !didReport) checkNarrowingProperty(property);
      },
      VariableDeclarator: declarator => {
        const didReport = redundant ? checkRedundantVariable(declarator) : false;
        if (narrowing && !didReport) checkNarrowingVariable(declarator);
      },
    };
  },
  defaultOptions: [{ narrowing: true, redundant: true }],
  meta: {
    docs: {
      description:
        "Disallow type annotations that add nothing — either restating a type TypeScript already infers (`redundant`) or narrowing a value to a supertype that hides members it actually has (`narrowing`) — and remove or suggest removing them. Each concern is an independent option, `error` by default, so a config may enforce one without the other. The cheap `redundant` checks run first and a redundant report short-circuits the type-comparing `narrowing` pass for the same node. `redundant` (autofix), exempt at a module boundary (exported declarations, whose annotations may be load-bearing for declaration emit): (1) arrow-function return types — skipping type predicates, generic returns that reference a type parameter, and recursive arrows; (2) arrow parameters whose type is fixed by a contextual function type independent of the annotation (`arr.map((x: number) => …)`, `const f: (a: T) => … = (a: T) => …`) — a parameter with no contextual type, one that widens past it, or one whose contextual type merely echoes the annotation (a self-referential `Object.assign` source object, or a generic higher-order function that infers its own type parameter from the callback, `pipe<A>(f: (a: A) => void)`) keeps its annotation; (3) `const`/`let`/class-property declarations whose annotation matches the type inferred from a self-determined initializer (identifier, member access, template literal, unary or binary expression) — call/`new`/object/array/arrow initializers are left alone, since their inferred type can depend on the annotation. `narrowing` (suggestion, since removal widens the exposed type), applied everywhere including exported declarations — narrowing discards information regardless of visibility, so there is no module-boundary excuse: function return types (arrow, function, and method, comparing the annotation against the members common to every `return`) and `const`/`let`/class-field declarations. Skipped: type predicates, recursive functions, generic returns referencing a type parameter, async and generator functions, and a reassigned `let` or class field (whose wider annotation may be load-bearing for a later assignment). Only annotations that hide a member are reported, so an index-signature ('open dictionary') type, erasure to `any`/`unknown`/`{}`, and literal widening (`number` for `5`) never are — while narrowing through any named type, base class, interface, or readonly collection view such as `ReadonlySet` or `readonly T[]` is — as is a bare function or constructor type that drops a property the callable value actually carries (`const f: (x: number) => void = callableWithExtraProp`).",
      requiresTypeChecking: true,
    },
    fixable: 'code',
    hasSuggestions: true,
    messages: {
      narrowReturnType:
        'This return type hides member(s) the returned value has: {{members}}. Narrowing discards information — remove the annotation to expose the full inferred type, or return a value that genuinely has only these members.',
      narrowVarType:
        'This type annotation hides member(s) the value has: {{members}}. Narrowing discards information — remove the annotation to keep the full inferred type, or assign a value that genuinely has only these members.',
      removeAnnotation: 'Remove the narrowing annotation and keep the full inferred type.',
      removeParamType:
        'Parameter type annotation is redundant; its type is already fixed by the contextual function type. Let TypeScript infer it. (Parameters with no contextual type, and exported functions, are exempt.)',
      removeReturnType:
        'Explicit return type annotation is unnecessary; let TypeScript infer it. (Exported functions are exempt, since `tsc` may need the annotation for declaration-emit portability.)',
      removeVarType:
        'Type annotation is redundant; it restates the type already inferred from the initializer. Let TypeScript infer it. (Exported declarations are exempt, since `tsc` may need the annotation for declaration-emit portability.)',
    },
    schema: [
      {
        additionalProperties: false,
        properties: {
          narrowing: { type: 'boolean' },
          redundant: { type: 'boolean' },
        },
        type: 'object',
      },
    ],
    type: 'suggestion',
  },
  name: 'no-type-annotations',
});
