import { ensure } from '@zyplux/util/assert';
import { run } from '@zyplux/util/exec';
import { $, readTrimmed } from '@zyplux/util/shell';
import { mkdtempDisposable, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import type { ReleaseTarget } from './release-targets.ts';

import { ContainerDigestSchema } from './contracts.ts';
import { isReleasePublished, publishReleaseAssets } from './github-releases.ts';

export const CONTAINER_MANIFEST = 'release.json';

export const publishContainer = async (target: ReleaseTarget, notes: string) => {
  const { container, label, tag, version } = target;
  ensure(container !== undefined, 'container publication requires a GHCR target');
  if (await isReleasePublished(tag, [CONTAINER_MANIFEST])) {
    ensure(await target.isPublished(), `published release ${tag} is missing image ${label}:${version}`);
    return;
  }
  const token = process.env['GH_TOKEN'];
  const actor = process.env['GITHUB_ACTOR'];
  ensure(token !== undefined && token.length > 0, 'GH_TOKEN is required to push to GHCR');
  ensure(actor !== undefined && actor.length > 0, 'GITHUB_ACTOR is required to push to GHCR');
  const revision = await readTrimmed($.git.revParse('HEAD'));
  const versioned = `${label}:${version}`;
  await using directory = await mkdtempDisposable(path.join(tmpdir(), 'airlock-container-'));
  const digestFile = path.join(directory.path, 'digest');
  const manifest = path.join(directory.path, CONTAINER_MANIFEST);
  await run(['podman', 'login', 'ghcr.io', '-u', actor, '--password-stdin'], { stdin: token });
  try {
    const dockerfile = container.dockerfile === undefined ? [] : ['--file', container.dockerfile];
    await $`podman build ${dockerfile} --label ${`org.opencontainers.image.version=${version}`} --label ${`org.opencontainers.image.revision=${revision}`} -t ${versioned} ${container.buildContext}`;
    await $`podman push --digestfile ${digestFile} ${versioned}`;
    const digest = ContainerDigestSchema.parse(await readFile(digestFile, 'utf8'));
    ensure(await target.isPublished(), `container push did not publish image ${versioned}`);
    await writeFile(manifest, `${JSON.stringify({ image: `${label}@${digest}`, version })}\n`);
  } finally {
    await $`podman logout ghcr.io`;
  }
  await publishReleaseAssets(tag, notes, revision, [manifest]);
};
