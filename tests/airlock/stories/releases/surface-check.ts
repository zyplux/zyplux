import type { SurfaceFinding } from '@zyplux/airlock/contracts';
import type { CliRunner } from '@zyplux/spectra/cli-runner';

import { SurfaceFindingsSchema } from '@zyplux/airlock/contracts';
import { notFoundResponse } from '@zyplux/spectra/fetch-fake';
import { parseJson } from '@zyplux/util/json';
import { attemptAsync } from '@zyplux/util/result';
import { expect } from 'vitest';

import type { ReleaseTest } from './releases.ts';

const MANIFEST = `scope = "@zyplux"
[util]
kind = "npm"
surface = ["packages/util/src"]
version = { file = "packages/util/package.json", json = "version" }
`;

export const extendSurfaceChecks = (test: ReleaseTest) =>
  test.extend<{
    checkSurface: (base?: string) => Promise<SurfaceFinding[]>;
    setBaseVersion: (version?: string) => Promise<void>;
    setPublishedVersion: (version?: string) => void;
    surfaceCli: CliRunner;
  }>({
    checkSurface: async ({ logs, surfaceCli }, use) => {
      await use(async base => {
        const outcome = await attemptAsync(() =>
          surfaceCli.run('check-surface', '--json', ...(base === undefined ? [] : ['--base', base])),
        );
        const findings = parseJson(logs.logLines.at(-1) ?? '', SurfaceFindingsSchema);
        expect(outcome.ok).toBe(findings.every(finding => finding.status === 'pass' || finding.status === 'skip'));
        if (!outcome.ok) expect(outcome.error).toMatchObject({ message: 'release surface validation failed' });
        return findings;
      });
    },
    setBaseVersion: async ({ loadArtifact, shell }, use) => {
      await use(async version => {
        const manifest = await loadArtifact('airlock-targets.toml');
        shell.on(
          'git ls-tree --name-only origin/main -- airlock-targets.toml',
          version === undefined ? '' : 'airlock-targets.toml',
        );
        shell.on('git show origin/main:airlock-targets.toml', manifest);
        shell.on('git ls-tree --name-only origin/main -- packages/util/package.json', 'packages/util/package.json');
        shell.on('git show origin/main:packages/util/package.json', JSON.stringify({ version }));
      });
    },
    setPublishedVersion: async ({ network, shell }, use) => {
      await use(version => {
        for (const registry of ['https://registry.npmjs.org/', 'https://npm.pkg.github.com/'])
          network.on(registry, () =>
            version === undefined ? notFoundResponse() : Response.json({ 'dist-tags': { latest: version } }),
          );
        network.on('https://pypi.org/', () =>
          version === undefined ? notFoundResponse() : Response.json({ info: { version } }),
        );
        network.on('https://ghcr.io/token', () => Response.json({ token: 'image-token' }));
        network.on('https://ghcr.io/v2/', () => Response.json({ tags: version === undefined ? [] : [version] }));
        shell.on(
          'gh api --paginate --slurp',
          JSON.stringify([
            version === undefined ? [] : [{ draft: false, prerelease: false, tag_name: `util-v${version}` }],
          ]),
        );
      });
    },
    surfaceCli: async ({ airlock, env, setPublishedVersion, shell, targets, tempDir }, use) => {
      env.set('GITHUB_BASE_REF', '');
      await tempDir.write('airlock-targets.toml', MANIFEST);
      shell.on('git ls-tree', '');
      shell.on('git diff --name-only', '');
      setPublishedVersion(targets.util.version);
      await use(airlock);
    },
  });
