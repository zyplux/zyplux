import type { ShellFake } from '@zyplux/spectra/shell-fake';

import { ensure } from '@zyplux/util/assert';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';

import type { Registries } from './release-scenario.ts';

const DIGEST_HEX_LENGTH = 64;
const RELEASE_ASSET_ARGUMENT = 3;

export const createContainerPublication = (shell: ShellFake, registries: Registries) => {
  let manifest = '';
  let builds = 0;
  shell.on('podman', '');
  shell.on('uv run', () => {
    builds += 1;
    const environment = shell.calls.at(-1)?.env;
    const directory = environment?.['AIRLOCK_ARTIFACTS_DIR'];
    ensure(directory !== undefined, 'artifact command needs a temporary directory');
    writeFileSync(
      path.join(directory, 'release.json'),
      JSON.stringify({
        coreVersion: environment?.['AIRLOCK_VERSION'],
        image: `${environment?.['AIRLOCK_IMAGE']}@sha256:${String(builds).repeat(DIGEST_HEX_LENGTH)}`,
        revision: environment?.['AIRLOCK_REVISION'],
        validatorVersion: '1.2.3',
      }),
    );
    registries.setPublished({ ghcrPublished: true });
    return '';
  });
  shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');
  shell.on('gh release upload', () => {
    const artifact = shell.calls.at(-1)?.argv[RELEASE_ASSET_ARGUMENT];
    ensure(artifact !== undefined, 'release upload requires its artifact');
    manifest = readFileSync(artifact, 'utf8');
    return '';
  });
  shell.on('gh release edit', '');
  return { readManifest: () => manifest };
};
