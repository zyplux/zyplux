import type { SourceSnapshot } from '@zyplux/cz/contracts';
import type { ShellFake } from '@zyplux/spectra/shell-fake';
import type { TempDir } from '@zyplux/spectra/temp-directory';

import { readFile } from 'node:fs/promises';
import path from 'node:path';

import { workspaceTest } from '#workspace-test';

const createReports = (tempDir: TempDir, shell: ShellFake) => {
  type Classification = SourceSnapshot[string];
  const files: SourceSnapshot = {};
  shell.on('git rev-parse --show-toplevel', tempDir.path);
  shell.on('uv run --no-sync cerberus source-oracle', () => JSON.stringify(files));
  return {
    graph: () => readFile(path.join(tempDir.path, 'WORKSPACE_GRAPH.md'), 'utf8'),
    write: async (file: string, content: string, classification: Partial<Classification> = {}) => {
      files[file] = { is_test: false, kind: 'prod', needs_tests: true, root: '.', ...classification };
      return tempDir.write(file, content);
    },
    writePackage: async (
      directory: string,
      name: string,
      dependencies = {},
      classification: Partial<Classification> = {},
    ) => {
      const file = path.posix.join(directory, 'package.json');
      files[file] = { is_test: false, kind: 'prod', needs_tests: true, root: directory, ...classification };
      return tempDir.write(file, JSON.stringify({ name, version: '1.0.0', ...dependencies }));
    },
  };
};

export type ReportRepo = ReturnType<typeof createReports>;

export const test = workspaceTest.extend('reports', ({ shell, tempDir }) => createReports(tempDir, shell));
export { describe, expect } from 'vitest';
