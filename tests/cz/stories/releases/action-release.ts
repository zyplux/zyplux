import type { ShellFake } from '@zyplux/spectra/shell-fake';
import type { TempDir } from '@zyplux/spectra/temp-directory';

import { PythonReleaseSchema } from '@zyplux/cz/contracts';
import { parseJson } from '@zyplux/util/json';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';
import { vi } from 'vitest';

import type { Repo } from '#repository-fake';

import { seedReleaseTargets } from './release-scenario.ts';

export type ActionRelease = Awaited<ReturnType<typeof createActionRelease>>;
type ActionContext = { repo: Repo; shell: ShellFake; tempDir: TempDir };
type PublishedRelease = string | { draft?: boolean; prerelease?: boolean; tag: string };

export const createActionRelease = async ({ repo, shell, tempDir }: ActionContext) => {
  vi.mocked(sleep).mockResolvedValue(undefined);
  const targets = await seedReleaseTargets(tempDir);
  await tempDir.write(
    'release-targets.toml',
    `[[target]]
  kind = "action"
  label = "zyplux-setup-pm"
  repository = "zyplux/zyplux"
  surface = ["setup-pm", "apps/setup-pm/src"]
  tag_prefix = "setup-pm-v"
  major_tag_prefix = "v"
  version = { file = "apps/setup-pm/pyproject.toml", regex = '^version = "([^"]+)"' }
  `,
  );
  await tempDir.write('apps/setup-pm/pyproject.toml', '[project]\nname = "zyplux-setup-pm"\nversion = "1.0.0"\n');
  await tempDir.write(
    'apps/setup-pm/package.json',
    JSON.stringify({ name: 'zyplux-setup-pm', private: true, version: '1.0.0' }),
  );
  await tempDir.write('apps/setup-pm/CHANGELOG.md', '# Releases\n\n## 1.0.0\n\n- Cache package managers.\n');
  repo.setHeadSha('reviewed-sha');
  repo.setRepoSlug('zyplux/zyplux');
  shell.on('gh api graphql', '{"data":{"repository":{"release":{"id":"release-id"}}}}');
  shell.on('git ls-remote origin refs/tags/v1', 'old-sha\trefs/tags/v1');
  shell.on('git ls-remote origin refs/tags/setup-pm-v1.0.0*', 'release-sha\trefs/tags/setup-pm-v1.0.0');
  shell.on('git rev-parse FETCH_HEAD^{commit}', 'release-sha');
  const setPublished = (...pages: PublishedRelease[][]) => {
    shell.on(
      'gh api --paginate --slurp',
      JSON.stringify(
        pages.map(page =>
          page.map(release => ({
            draft: typeof release === 'string' ? false : (release.draft ?? false),
            prerelease: typeof release === 'string' ? false : (release.prerelease ?? false),
            tag_name: typeof release === 'string' ? release : release.tag,
          })),
        ),
      ),
    );
  };
  setPublished(['setup-pm-v1.0.0']);
  return {
    loadVersion: async () =>
      parseJson(await readFile(path.join(tempDir.path, 'apps/setup-pm/package.json'), 'utf8'), PythonReleaseSchema)
        .version,
    setPublished,
    targets,
  };
};
