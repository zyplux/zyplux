import type { SourceSnapshot } from '@zyplux/cz/contracts';
import type { ShellFake } from '@zyplux/spectra/shell-fake';
import type { TempDir } from '@zyplux/spectra/temp-directory';

import { readFile } from 'node:fs/promises';
import path from 'node:path';

import { workspaceTest } from '#workspace-test';

export type DependencyField = 'dependencies' | 'devDependencies' | 'optionalDependencies' | 'peerDependencies';

const createReports = (tempDir: TempDir, shell: ShellFake) => {
  type Classification = Partial<Pick<SourceSnapshot[string], 'is_test' | 'kind'>>;
  type PackageOptions = Partial<Record<DependencyField, Record<string, string>>> & { classification?: Classification };
  const files: SourceSnapshot = {};
  shell.on('git rev-parse --show-toplevel', tempDir.path);
  shell.on('uv run --no-sync cerberus source-oracle', () => JSON.stringify(files));

  const writeFile = (
    file: string,
    content: string,
    root: string,
    { is_test: isTest = false, kind = 'prod' }: Classification = {},
  ) => {
    files[file] = { is_test: isTest, kind, needs_tests: true, root };
    return tempDir.write(file, content);
  };

  return {
    graph: () => readFile(path.join(tempDir.path, 'WORKSPACE_GRAPH.md'), 'utf8'),
    write: (file: string, content: string, classification?: Classification) =>
      writeFile(file, content, '.', classification),
    writePackage: (directory: string, name: string, { classification, ...dependencies }: PackageOptions = {}) =>
      writeFile(
        path.posix.join(directory, 'package.json'),
        JSON.stringify({ name, version: '1.0.0', ...dependencies }),
        directory,
        classification,
      ),
  };
};

export type ReportRepo = ReturnType<typeof createReports>;

export const test = workspaceTest.extend('reports', ({ shell, tempDir }) => createReports(tempDir, shell));
export { describe, expect } from 'vitest';
