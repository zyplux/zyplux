import { collectModuleReferences } from '@zyplux/util/module-references';
import { findTypeDependencyViolations } from '@zyplux/util/type-dependencies';
import ts from 'typescript';

export const PACKAGES = [
  { directory: 'apps/client', exports: { '.': './src/index.ts' }, name: '@example/client' },
  { directory: 'packages/component', exports: { '.': './src/index.ts' }, name: '@example/component' },
  {
    directory: 'packages/domain-model',
    exports: { './contracts': './src/contracts.ts' },
    name: '@example/domain-model',
  },
];

export const checkTypeDependencies = (sources: Record<string, string>, packages = PACKAGES) =>
  findTypeDependencyViolations({
    imports: Object.entries(sources).flatMap(([filePath, source]) =>
      collectModuleReferences(ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true)),
    ),
    packages,
    sharedTypeSurfaces: new Set(['contracts']),
  });
