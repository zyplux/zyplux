import { existsSync, globSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { parse as parseYaml } from 'yaml';

import { ArchitectureConfigSchema, ArchitecturePackageSchema, WorkspaceConfigSchema } from './contracts.ts';
import { parseJson } from './json.ts';
import { parseToml } from './toml.ts';

export const loadArchitecture = (root: string) => {
  const file = path.join(root, 'cerberus.toml');
  return (
    existsSync(file)
      ? parseToml(readFileSync(file, 'utf8'), ArchitectureConfigSchema)
      : ArchitectureConfigSchema.parse({})
  ).architecture;
};

export const listWorkspacePackages = (root: string) => {
  const workspace = path.join(root, 'pnpm-workspace.yaml');
  const patterns = existsSync(workspace)
    ? WorkspaceConfigSchema.parse(parseYaml(readFileSync(workspace, 'utf8'))).packages
    : ['.'];
  if (patterns.length === 0) patterns.push('.');
  const excluded = patterns.filter(pattern => pattern.startsWith('!')).map(pattern => pattern.slice(1));
  return [
    ...new Set(
      patterns
        .filter(pattern => !pattern.startsWith('!'))
        .flatMap(pattern => (pattern === '.' ? '.' : [...globSync(pattern, { cwd: root, exclude: excluded })])),
    ),
  ].flatMap(directory => {
    const manifest = path.join(root, directory, 'package.json');
    return existsSync(manifest)
      ? {
          ...parseJson(readFileSync(manifest, 'utf8'), ArchitecturePackageSchema),
          directory: path.resolve(root, directory),
        }
      : [];
  });
};

export const buildExportMap = (exports: unknown): Record<string, unknown> => {
  if (exports === null || exports === undefined) return {};
  return typeof exports === 'object' && !Array.isArray(exports) && Object.keys(exports).some(key => key.startsWith('.'))
    ? Object.fromEntries(Object.entries(exports))
    : { '.': exports };
};

export const listExportTargets = (target: unknown): string[] => {
  if (typeof target === 'string') return [target];
  return target === null || typeof target !== 'object'
    ? []
    : Object.values(target).flatMap(child => listExportTargets(child));
};

export const hasPublicExport = (exports: unknown, key: string) => {
  const entries = buildExportMap(exports);
  if (Object.hasOwn(entries, key)) return listExportTargets(entries[key]).length > 0;
  const patterns = Object.keys(entries)
    .filter(candidate => candidate.includes('*'))
    .toSorted((left, right) => right.indexOf('*') - left.indexOf('*') || right.length - left.length);
  const matched = patterns.find(candidate => {
    const wildcard = candidate.indexOf('*');
    const prefix = candidate.slice(0, wildcard);
    const suffix = candidate.slice(wildcard + '*'.length);
    return key.startsWith(prefix) && key.endsWith(suffix) && key.length >= prefix.length + suffix.length;
  });
  return matched !== undefined && listExportTargets(entries[matched]).length > 0;
};

type PackageLocation = { directory: string; name: string };
export const findPackageOwner = <Package extends PackageLocation>(file: string, packages: readonly Package[]) =>
  packages
    .filter(({ directory }) => {
      const relative = path.relative(directory, file);
      return relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
    })
    .toSorted((left, right) => right.directory.length - left.directory.length)[0];
