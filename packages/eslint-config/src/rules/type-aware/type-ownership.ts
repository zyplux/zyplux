import type { ParserServicesWithTypeInformation } from '@typescript-eslint/utils';

import { collectModuleReferences } from '@zyplux/util/module-references';
import { findTypeDependencyViolations } from '@zyplux/util/type-dependencies';
import { findPackageOwner, listWorkspacePackages } from '@zyplux/util/workspace-architecture';
import ts from 'typescript';

const cache = new WeakMap<ts.Program, ReturnType<typeof findTypeViolations>>();

const findTypeViolations = (program: ts.Program, root: string) => {
  const packages = listWorkspacePackages(root);
  const imports = program
    .getSourceFiles()
    .filter(source => !source.isDeclarationFile && findPackageOwner(source.fileName, packages) !== undefined)
    .flatMap(source => collectModuleReferences(source))
    .map(reference => ({
      ...reference,
      resolvedFile: ts.resolveModuleName(reference.specifier, reference.filePath, program.getCompilerOptions(), ts.sys)
        .resolvedModule?.resolvedFileName,
    }));
  return findTypeDependencyViolations({
    imports,
    packages,
    sharedTypeSurfaces: new Set(['contracts', 'interfaces']),
  });
};

export const getTypeViolations = (services: ParserServicesWithTypeInformation, root: string) => {
  const { program } = services;
  const stored = cache.get(program);
  if (stored !== undefined) return stored;
  const violations = findTypeViolations(program, root);
  cache.set(program, violations);
  return violations;
};
