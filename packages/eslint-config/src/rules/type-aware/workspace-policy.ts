import type { ParserServicesWithTypeInformation } from '@typescript-eslint/utils';

import { collectModuleReferences } from '@zyplux/util/module-references';
import { findTypeDependencyViolations } from '@zyplux/util/type-dependencies';
import { findPackageOwner, listWorkspacePackages, loadArchitecture } from '@zyplux/util/workspace-architecture';
import ts from 'typescript';

const cache = new WeakMap<ts.Program, ReturnType<typeof buildWorkspacePolicy>>();

const buildWorkspacePolicy = (program: ts.Program, root: string) => {
  const packages = listWorkspacePackages(root);
  const architecture = loadArchitecture(root);
  const imports = program
    .getSourceFiles()
    .filter(source => !source.isDeclarationFile && findPackageOwner(source.fileName, packages) !== undefined)
    .flatMap(source => collectModuleReferences(source))
    .map(reference => ({
      ...reference,
      resolvedFile: ts.resolveModuleName(reference.specifier, reference.filePath, program.getCompilerOptions(), ts.sys)
        .resolvedModule?.resolvedFileName,
    }));
  const violations = findTypeDependencyViolations({
    imports,
    packages,
    sharedTypeSurfaces: new Set(['contracts', 'interfaces']),
  });
  return { architecture, imports, packages, violations };
};

export const getWorkspacePolicy = (services: ParserServicesWithTypeInformation, root: string) => {
  const { program } = services;
  const stored = cache.get(program);
  if (stored !== undefined) return stored;
  const policy = buildWorkspacePolicy(program, root);
  cache.set(program, policy);
  return policy;
};

export const findImportViolation = (
  specifier: string,
  file: string,
  services: ParserServicesWithTypeInformation,
  root: string,
) => {
  const { architecture, packages } = getWorkspacePolicy(services, root);
  const consumer = findPackageOwner(file, packages);
  const resolved = ts.resolveModuleName(specifier, file, services.program.getCompilerOptions(), ts.sys).resolvedModule
    ?.resolvedFileName;
  const provider =
    packages.find(candidate => specifier === candidate.name || specifier.startsWith(`${candidate.name}/`)) ??
    (resolved === undefined ? undefined : findPackageOwner(resolved, packages));
  if (consumer === undefined || provider === undefined || consumer === provider) return;
  const allowed = architecture.dependencies[consumer.name];
  if (allowed !== undefined && !allowed.includes(provider.name))
    return `${consumer.name} cannot depend on ${provider.name}; this reverses the declared ownership direction.`;
  return;
};
