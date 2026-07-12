import type { TSESTree } from '@typescript-eslint/utils';

import { ESLintUtils } from '@typescript-eslint/utils';
import * as ts from 'typescript';

import { createRule } from '#create-rule';

type MessageId = 'unusedExportedType' | 'unusedLocalType';

type TypeDeclaration = ts.InterfaceDeclaration | ts.TypeAliasDeclaration;

const isDeclarationName = (node: ts.Identifier) => {
  const { parent } = node;
  return (ts.isTypeAliasDeclaration(parent) || ts.isInterfaceDeclaration(parent)) && parent.name === node;
};

const isSpecifierName = (node: ts.Identifier) => {
  const { parent } = node;
  if (ts.isImportSpecifier(parent) || ts.isExportSpecifier(parent)) {
    return parent.name === node || parent.propertyName === node;
  }
  return false;
};

const hasExportModifier = (node: TypeDeclaration) =>
  ts.getModifiers(node)?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword) ?? false;

const isDeclarationMerge = ({ parent }: TypeDeclaration) =>
  ts.findAncestor(parent, ts.isModuleDeclaration) !== undefined;

const resolveSymbol = (checker: ts.TypeChecker, symbol: ts.Symbol) => {
  let resolved = symbol;
  while ((resolved.flags & ts.SymbolFlags.Alias) !== 0) resolved = checker.getAliasedSymbol(resolved);
  return resolved;
};

const collectUsedSymbols = (program: ts.Program, checker: ts.TypeChecker) => {
  const used = new Set<ts.Symbol>();
  const visit = (node: ts.Node): void => {
    if (ts.isIdentifier(node) && !isDeclarationName(node) && !isSpecifierName(node)) {
      const symbol = checker.getSymbolAtLocation(node);
      if (symbol !== undefined) used.add(resolveSymbol(checker, symbol));
    }
    ts.forEachChild(node, visit);
  };
  for (const sourceFile of program.getSourceFiles()) {
    if (sourceFile.isDeclarationFile || program.isSourceFileFromExternalLibrary(sourceFile)) continue;
    visit(sourceFile);
  }
  return used;
};

const usedSymbolsByProgram = new WeakMap<ts.Program, Set<ts.Symbol>>();

const getUsedSymbols = (program: ts.Program, checker: ts.TypeChecker) => {
  const cached = usedSymbolsByProgram.get(program);
  if (cached !== undefined) return cached;
  const used = collectUsedSymbols(program, checker);
  usedSymbolsByProgram.set(program, used);
  return used;
};

export const noPackageWideUnusedTypes = createRule<[], MessageId>({
  create: context => {
    const services = ESLintUtils.getParserServices(context);
    const checker = services.program.getTypeChecker();

    const checkDeclaration = (node: TSESTree.TSInterfaceDeclaration | TSESTree.TSTypeAliasDeclaration) => {
      const tsNode = services.esTreeNodeToTSNodeMap.get(node);
      if (isDeclarationMerge(tsNode)) return;

      const symbol = checker.getSymbolAtLocation(tsNode.name);
      if (symbol === undefined) return;

      const used = getUsedSymbols(services.program, checker);
      if (used.has(symbol)) return;

      const messageId: MessageId = hasExportModifier(tsNode) ? 'unusedExportedType' : 'unusedLocalType';
      context.report({ data: { name: tsNode.name.text }, messageId, node: node.id });
    };

    return {
      TSInterfaceDeclaration: checkDeclaration,
      TSTypeAliasDeclaration: checkDeclaration,
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description:
        "Flag a `type`/`interface` that is never referenced anywhere else within its own package — whether exported or not, and regardless of whether it is only re-exported (e.g. through a barrel `index.ts`) or not referenced at all. Type-aware: the check walks every non-declaration source file in the program (a program is built from one package's `tsconfig.json`, so this is a package-boundary check, not a whole-monorepo one) and resolves every identifier through the type checker, skipping only the declaration's own name and import/export specifier names — those are re-binding, not use. A type referenced anywhere in a type position within the package (a parameter, a property, a heritage clause, a generic argument, a barrel re-export's consumer) counts as used; a type that only ever appears as its own declaration or as the target of `import`/`export … from` specifiers does not. An unused non-exported type is dead code local to the package; an unused exported type is either dead code too, or a type that belongs in whichever package actually consumes it — the message differs accordingly. A declaration-merging interface inside a `declare module`/`declare global` block is exempt: it is never referenced by name, only structurally merged. This deliberately fires on legitimate public-API types in a contracts/domain package meant purely for other packages to consume — scope the rule with `ignores` where that is the intent.",
      requiresTypeChecking: true,
    },
    messages: {
      unusedExportedType:
        '`{{name}}` is exported but never used anywhere else within this package. If another package consumes it, move it to a package both sides can depend on, or colocate it with that consumer; if nothing consumes it, delete it.',
      unusedLocalType: '`{{name}}` is declared but never used anywhere in this package. Delete it.',
    },
    schema: [],
    type: 'suggestion',
  },
  name: 'no-package-wide-unused-types',
});
