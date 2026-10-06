import path from 'node:path';
import ts from 'typescript';

import type { ModuleReference } from './module-references.ts';

import { collectModuleReferences } from './module-references.ts';
import { findPackageOwner, hasPublicExport } from './workspace-architecture.ts';

type PackageImportCheck = {
  imports: readonly ModuleReference[];
  packages: readonly SourcePackage[];
};

type SourcePackage = {
  directory: string;
  exports?: unknown;
  name: string;
};

const findProvider = ({ filePath, resolvedFile, specifier }: ModuleReference, packages: readonly SourcePackage[]) => {
  if (resolvedFile !== undefined) return findPackageOwner(resolvedFile, packages);
  return specifier.startsWith('.')
    ? findPackageOwner(path.join(path.dirname(filePath), specifier), packages)
    : packages.find(item => specifier === item.name || specifier.startsWith(`${item.name}/`));
};

export const collectPackageReferences = ({ imports, packages }: PackageImportCheck) =>
  imports.flatMap(reference => {
    const consumer = findPackageOwner(reference.filePath, packages);
    const provider = findProvider(reference, packages);
    if (consumer === undefined || provider === undefined || consumer === provider) return [];
    const exportKey =
      reference.specifier === provider.name || reference.specifier.startsWith(`${provider.name}/`)
        ? `.${reference.specifier.slice(provider.name.length)}`
        : '';
    return { ...reference, consumer, exportKey, provider };
  });

type PackageReference = ReturnType<typeof collectPackageReferences>[number];

export const findTypeExportViolations = (references: readonly PackageReference[]) =>
  references.filter(
    reference => reference.hasTypeBindings && !hasPublicExport(reference.provider.exports, reference.exportKey),
  );

type TypeDependencyCheck = {
  references: readonly PackageReference[];
  sharedTypeSurfaces: ReadonlySet<string>;
};

export const findTypeOnlyDependencies = ({ references, sharedTypeSurfaces }: TypeDependencyCheck) => {
  const runtimeDependencies = new Set(
    references
      .filter(
        reference => reference.hasValueBindings && hasPublicExport(reference.provider.exports, reference.exportKey),
      )
      .map(({ consumer, provider }) => `${consumer.name}:${provider.name}`),
  );

  return references.filter(
    ({ consumer, exportKey, hasTypeBindings, provider }) =>
      hasTypeBindings &&
      hasPublicExport(provider.exports, exportKey) &&
      !sharedTypeSurfaces.has(exportKey.replace(/^\.\//, '')) &&
      !runtimeDependencies.has(`${consumer.name}:${provider.name}`),
  );
};

type TypeDependencyScan = {
  packages: readonly SourcePackage[];
  program: ts.Program;
  sharedTypeSurfaces: ReadonlySet<string>;
};

export const scanTypeDependencies = ({ packages, program, sharedTypeSurfaces }: TypeDependencyScan) => {
  const compilerOptions = program.getCompilerOptions();
  const imports = program
    .getSourceFiles()
    .filter(source => !source.isDeclarationFile && findPackageOwner(source.fileName, packages) !== undefined)
    .flatMap(source => collectModuleReferences(source))
    .map(reference => ({
      ...reference,
      resolvedFile: ts.resolveModuleName(reference.specifier, reference.filePath, compilerOptions, ts.sys)
        .resolvedModule?.resolvedFileName,
    }));
  const references = collectPackageReferences({ imports, packages });
  return {
    typeOnlyDependencies: findTypeOnlyDependencies({ references, sharedTypeSurfaces }),
    unexportedTypes: findTypeExportViolations(references),
  };
};
