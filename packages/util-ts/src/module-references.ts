import ts from 'typescript';

export type ModuleReference = {
  filePath: string;
  hasTypeBindings: boolean;
  hasValueBindings: boolean;
  isTypeOnly: boolean;
  line: number;
  specifier: string;
};

const getImportReference = ({ importClause, moduleSpecifier }: ts.ImportDeclaration) => {
  const isTypeOnly = importClause?.phaseModifier === ts.SyntaxKind.TypeKeyword;
  const bindings = importClause?.namedBindings;
  const namedImports = bindings !== undefined && ts.isNamedImports(bindings) ? bindings.elements : [];
  return {
    hasTypeBindings: isTypeOnly || namedImports.some(binding => binding.isTypeOnly),
    hasValueBindings:
      !isTypeOnly &&
      (importClause?.name !== undefined ||
        (bindings !== undefined && ts.isNamespaceImport(bindings)) ||
        namedImports.some(binding => !binding.isTypeOnly)),
    isTypeOnly,
    specifierNode: moduleSpecifier,
  };
};

const getExportReference = ({ exportClause, isTypeOnly, moduleSpecifier }: ts.ExportDeclaration) => {
  if (moduleSpecifier === undefined) return;
  const namedExports = exportClause !== undefined && ts.isNamedExports(exportClause) ? exportClause.elements : [];
  return {
    hasTypeBindings: isTypeOnly || namedExports.some(binding => binding.isTypeOnly),
    hasValueBindings:
      !isTypeOnly &&
      (exportClause === undefined ||
        ts.isNamespaceExport(exportClause) ||
        namedExports.some(binding => !binding.isTypeOnly)),
    isTypeOnly,
    specifierNode: moduleSpecifier,
  };
};

const getModuleReference = (statement: ts.Statement) => {
  if (ts.isImportDeclaration(statement)) return getImportReference(statement);
  if (ts.isExportDeclaration(statement)) return getExportReference(statement);
  return;
};

export const collectModuleReferences = (sourceFile: ts.SourceFile) =>
  sourceFile.statements.flatMap(statement => {
    const reference = getModuleReference(statement);
    if (reference === undefined || !ts.isStringLiteral(reference.specifierNode)) return [];
    const specifier = reference.specifierNode.text;
    return [
      {
        filePath: sourceFile.fileName,
        hasTypeBindings: reference.hasTypeBindings,
        hasValueBindings: reference.hasValueBindings,
        isTypeOnly: reference.isTypeOnly,
        line: sourceFile.getLineAndCharacterOfPosition(statement.getStart(sourceFile)).line + 1,
        specifier,
      },
    ];
  });
