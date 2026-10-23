import type { ShellFake } from '@zyplux/spectra/shell-fake';

import { ensure } from '@zyplux/util/assert';
import { readFileSync, writeFileSync } from 'node:fs';

import type { Registries } from './release-scenario.ts';

const DIGEST_HEX_LENGTH = 64;
const RELEASE_ASSET_ARGUMENT = 3;

export const createContainerPublication = (shell: ShellFake, registries: Registries) => {
  let manifest = '';
  let builds = 0;
  let digest: string | undefined;
  let isImagePublished = true;
  shell.on('podman', '');
  shell.on('podman push --digestfile', () => {
    builds += 1;
    const argv = shell.calls.at(-1)?.argv;
    const digestFile = argv?.[argv.indexOf('--digestfile') + 1];
    ensure(digestFile !== undefined, 'container push must record its digest');
    writeFileSync(digestFile, digest ?? `sha256:${String(builds).repeat(DIGEST_HEX_LENGTH)}\n`);
    registries.setPublished({ ghcrPublished: isImagePublished });
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
  return {
    readManifest: () => manifest,
    setDigest: (next: string) => {
      digest = next;
    },
    setImagePublished: (isPublished: boolean) => {
      isImagePublished = isPublished;
    },
  };
};
