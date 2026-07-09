import type { CliRunner, ConsoleCapture, TempDir } from '@zyplux/tests-fixtures';

import { runCz } from '@zyplux/cz';
import { DepsCatalogSchema } from '@zyplux/cz/contracts';
import { createCliRunner } from '@zyplux/tests-fixtures';
import { parseJson } from '@zyplux/util';
import { execFileSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

import { workspaceRoot } from './arrange';

export type Catalog = {
  loadRepos: () => Promise<string[]>;
  outPath: string;
  readOutput: (relativePath?: string) => Promise<string>;
  run: (options?: RunCatalogOptions) => Promise<void>;
  runOverWorkspace: () => Promise<void>;
  unresolvedNames: (system: 'npm' | 'pypi') => string[];
  writeManifest: (relativePath: string, content: string) => Promise<void>;
};

type RunCatalogOptions = { out?: string };

export const createCz = () => createCliRunner(runCz);

export const createCatalog = (cz: CliRunner, tempDir: TempDir, { logLines }: ConsoleCapture) => {
  const outPath = path.join(tempDir.path, 'catalog.json');
  const readOutput = (relativePath = 'catalog.json') => readFile(path.join(tempDir.path, relativePath), 'utf8');
  const runGit = (...args: string[]) => {
    execFileSync('git', args, { cwd: tempDir.path, stdio: 'ignore' });
  };
  runGit('init', '--quiet');

  return {
    loadRepos: async () => parseJson(await readOutput(), DepsCatalogSchema),
    outPath,
    readOutput,
    run: async ({ out = 'catalog.json' }: RunCatalogOptions = {}) => {
      await cz.run('deps-catalog', '--dir', tempDir.path, '--out', out);
    },
    runOverWorkspace: async () => {
      await cz.run('deps-catalog', '--dir', workspaceRoot, '--out', outPath);
    },
    unresolvedNames: system => {
      const prefix = `  ${system}\t`;
      return logLines.filter(line => line.startsWith(prefix)).map(line => line.slice(prefix.length));
    },
    writeManifest: async (relativePath, content) => {
      await tempDir.write(relativePath, content);
      runGit('add', relativePath);
    },
  } satisfies Catalog;
};
