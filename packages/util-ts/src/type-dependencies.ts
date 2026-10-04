import path from 'node:path';

import type { ModuleReference } from './module-references.ts';

type SourcePackage = {
  directory: string;
  exports?: Readonly<Record<string, string>> | undefined;
  name: string;
};

type TypeDependencyCheck = {
  imports: readonly ModuleReference[];
  packages: readonly SourcePackage[];
  sharedTypeSurfaces: ReadonlySet<string>;
};

export const findTypeDependencyViolations = ({ imports, packages, sharedTypeSurfaces }: TypeDependencyCheck) => {
  const findOwner = (filePath: string) =>
    packages.find(({ directory }) => {
      const relative = path.relative(directory, filePath);
      return relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
    });
  const references = imports.flatMap(reference => {
    const consumer = findOwner(reference.filePath);
    const provider = reference.specifier.startsWith('.')
      ? findOwner(path.join(path.dirname(reference.filePath), reference.specifier))
      : packages.find(item => reference.specifier === item.name || reference.specifier.startsWith(`${item.name}/`));
    if (consumer === undefined || provider === undefined || consumer === provider) return [];
    const exportKey = `.${reference.specifier.slice(provider.name.length)}`;
    return [{ ...reference, consumer, exportKey, provider }];
  });
  const runtimeDependencies = new Set(
    references
      .filter(
        reference => reference.hasValueBindings && reference.provider.exports?.[reference.exportKey] !== undefined,
      )
      .map(({ consumer, provider }) => `${consumer.name}:${provider.name}`),
  );

  return references
    .filter(reference => reference.hasTypeBindings)
    .flatMap(reference => {
      const { consumer, exportKey, filePath, line, provider, specifier } = reference;
      const location = `${filePath}:${line} (${consumer.name} → ${provider.name}) '${specifier}'`;
      if (provider.exports?.[exportKey] === undefined) return [`${location}: not a public package entry`];
      if (sharedTypeSurfaces.has(exportKey.replace(/^\.\//, ''))) return [];
      return runtimeDependencies.has(`${consumer.name}:${provider.name}`)
        ? []
        : [`${location}: implementation package is used only for types`];
    });
};
