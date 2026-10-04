import ts from 'typescript';

export const isTypeExport = ({ declarations }: ts.Symbol) =>
  declarations?.some(
    declaration =>
      ts.isExportSpecifier(declaration) && (declaration.isTypeOnly || declaration.parent.parent.isTypeOnly),
  );

export const listRuntimeReexports = ({ statements }: ts.SourceFile, checker: ts.TypeChecker) =>
  new Map(
    statements.flatMap(statement => {
      if (!ts.isExportDeclaration(statement) || statement.isTypeOnly) return [];
      if (statement.exportClause !== undefined) {
        const names = ts.isNamedExports(statement.exportClause)
          ? statement.exportClause.elements.filter(element => !element.isTypeOnly).map(element => element.name.text)
          : [statement.exportClause.name.text];
        return names.map(name => [name, statement] as const);
      }
      const module =
        statement.moduleSpecifier === undefined ? undefined : checker.getSymbolAtLocation(statement.moduleSpecifier);
      return module === undefined
        ? []
        : checker.getExportsOfModule(module).map(symbol => [symbol.name, statement] as const);
    }),
  );

export const isMutableDeclaration = (declaration: ts.Declaration) =>
  ts.isVariableDeclaration(declaration) &&
  ts.isVariableDeclarationList(declaration.parent) &&
  !(declaration.parent.flags & ts.NodeFlags.Const);
