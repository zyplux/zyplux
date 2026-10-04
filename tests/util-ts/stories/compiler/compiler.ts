import { libraryTest } from '@zyplux/spectra';
import { collectModuleReferences } from '@zyplux/util/module-references';
import path from 'node:path';
import ts from 'typescript';

import { checkTypeDependencies, PACKAGES } from './type-dependency-fixture.ts';

const collectReferences = (source: string, filePath = 'caller.ts') =>
  collectModuleReferences(ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true));

export const test = libraryTest
  .extend('checkTypeDependencies', () => checkTypeDependencies)
  .extend('collectReferences', () => collectReferences)
  .extend('packages', () => PACKAGES)
  .extend('resolvePath', () => path.resolve);
export { expect } from 'vitest';
