import { libraryTest } from '@zyplux/spectra/library-test-api';
import { collectModuleReferences } from '@zyplux/util/module-references';
import {
  buildExportMap,
  findPackageOwner,
  hasPublicExport,
  listExportTargets,
  listWorkspacePackages,
} from '@zyplux/util/workspace-architecture';
import path from 'node:path';
import ts from 'typescript';

import { checkTypeDependencies, PACKAGES } from './type-dependency-fixture.ts';

const collectReferences = (source: string, filePath = 'caller.ts') =>
  collectModuleReferences(ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true));

export const test = libraryTest
  .extend('buildExportMap', () => buildExportMap)
  .extend('hasPublicExport', () => hasPublicExport)
  .extend('listExportTargets', () => listExportTargets)
  .extend('findPackageOwner', () => findPackageOwner)
  .extend('listWorkspacePackages', () => listWorkspacePackages)
  .extend('checkTypeDependencies', () => checkTypeDependencies)
  .extend('collectReferences', () => collectReferences)
  .extend('packages', () => PACKAGES)
  .extend('resolvePath', () => path.resolve);
export { expect } from 'vitest';
