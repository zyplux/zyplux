import type { CliRunner, ConsoleCapture, FetchFake, TempDir } from '@zyplux/tests-fixtures';

import { runCz } from '@zyplux/cz';
import { DepsCatalogSchema } from '@zyplux/cz/contracts';
import { createCliRunner } from '@zyplux/tests-fixtures';
import { parseJson } from '@zyplux/util';
import { execFileSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

export type Catalog = {
  loadRepos: () => Promise<string[]>;
  outPath: string;
  readOutput: (relativePath?: string) => Promise<string>;
  run: (options?: RunCatalogOptions) => Promise<void>;
  stubDepsDev: (sourceRepoByPackage: Record<string, DepsDevSourceRepo>) => void;
  stubNpmRegistry: (repoByName: Record<string, string>) => void;
  stubPypiRegistry: (repoByName: Record<string, string>) => void;
  unresolvedNames: (packageRegistry: 'npm' | 'pypi') => string[];
  writeManifest: (relativePath: string, content: string) => Promise<void>;
};

type DepsDevSourceRepo = string | { repo: string; via: 'links' };

type RunCatalogOptions = { out?: string };

const escapeRegExp = (text: string) => text.replaceAll(/[$()*+.?[\\\]^{|}]/g, String.raw`\$&`);

const depsDevDefaultVersion = () =>
  Response.json({ versions: [{ isDefault: true, versionKey: { version: '1.0.0' } }] });

const depsDevSourceRepoResponse = (sourceRepo: DepsDevSourceRepo) =>
  typeof sourceRepo === 'string'
    ? Response.json({ relatedProjects: [{ projectKey: { id: sourceRepo }, relationType: 'SOURCE_REPO' }] })
    : Response.json({ links: [{ label: 'SOURCE_REPO', url: `https://${sourceRepo.repo}` }] });

export const createCz = () => createCliRunner(runCz);

export const createCatalog = (cz: CliRunner, tempDir: TempDir, { logLines }: ConsoleCapture, network: FetchFake) => {
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
    stubDepsDev: sourceRepoByPackage => {
      for (const [key, sourceRepo] of Object.entries(sourceRepoByPackage)) {
        const [system, name] = key.split(':');
        const base = `https://api.deps.dev/v3/systems/${system}/packages/${encodeURIComponent(name ?? '')}`;
        network.on(new RegExp(`^${escapeRegExp(base)}$`), () => depsDevDefaultVersion());
        network.on(new RegExp(String.raw`^${escapeRegExp(base)}/versions/1\.0\.0$`), () =>
          depsDevSourceRepoResponse(sourceRepo),
        );
      }
    },
    stubNpmRegistry: repoByName => {
      for (const [name, repo] of Object.entries(repoByName)) {
        network.on(`https://registry.npmjs.org/${name.replace('/', '%2F')}/latest`, () =>
          Response.json({ repository: { url: `git+https://${repo}.git` } }),
        );
      }
    },
    stubPypiRegistry: repoByName => {
      for (const [name, repo] of Object.entries(repoByName)) {
        network.on(`https://pypi.org/pypi/${encodeURIComponent(name)}/json`, () =>
          Response.json({ info: { project_urls: { Source: `https://${repo}` } } }),
        );
      }
    },
    unresolvedNames: packageRegistry => {
      const prefix = `  ${packageRegistry}\t`;
      return logLines.filter(line => line.startsWith(prefix)).map(line => line.slice(prefix.length));
    },
    writeManifest: async (relativePath, content) => {
      await tempDir.write(relativePath, content);
      runGit('add', relativePath);
    },
  } satisfies Catalog;
};
