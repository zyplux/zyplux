import path from 'node:path';

import type { ModuleReference } from './module-references.ts';

import { findPackageOwner, hasPublicExport } from './workspace-architecture.ts';

type SourcePackage = {
  directory: string;
  exports?: unknown;
  name: string;
};

type TypeDependencyCheck = {
  imports: readonly ModuleReference[];
  packages: readonly SourcePackage[];
  sharedTypeSurfaces: ReadonlySet<string>;
};

export const findTypeDependencyViolations = ({ imports, packages, sharedTypeSurfaces }: TypeDependencyCheck) => {
  const references = imports.flatMap(reference => {
    const consumer = findPackageOwner(reference.filePath, packages);
    const provider =
      reference.resolvedFile === undefined
        ? reference.specifier.startsWith('.')
          ? findPackageOwner(path.join(path.dirname(reference.filePath), reference.specifier), packages)
          : packages.find(item => reference.specifier === item.name || reference.specifier.startsWith(`${item.name}/`))
        : findPackageOwner(reference.resolvedFile, packages);
    if (consumer === undefined || provider === undefined || consumer === provider) return [];
    const exportKey =
      reference.specifier === provider.name || reference.specifier.startsWith(`${provider.name}/`)
        ? `.${reference.specifier.slice(provider.name.length)}`
        : '';
    return { ...reference, consumer, exportKey, provider };
  });
  const runtimeDependencies = new Set(
    references
      .filter(
        reference => reference.hasValueBindings && hasPublicExport(reference.provider.exports, reference.exportKey),
      )
      .map(({ consumer, provider }) => `${consumer.name}:${provider.name}`),
  );

  return references
    .filter(reference => reference.hasTypeBindings)
    .flatMap(reference => {
      const { consumer, exportKey, filePath, line, provider, specifier } = reference;
      const location = `${filePath}:${line} (${consumer.name} → ${provider.name}) '${specifier}'`;
      if (!hasPublicExport(provider.exports, exportKey)) return `${location}: not a public package entry`;
      if (sharedTypeSurfaces.has(exportKey.replace(/^\.\//, ''))) return [];
      return runtimeDependencies.has(`${consumer.name}:${provider.name}`)
        ? []
        : `${location}: implementation package is used only for types`;
    });
};
