import { $, readTrimmed } from '@zyplux/util/shell';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import * as z from 'zod';

export const createGithubRelease = async (tag: string, notes: string, commit: string) => {
  const directory = await mkdtemp(path.join(tmpdir(), 'cz-release-'));
  try {
    const notesFile = path.join(directory, 'release-notes.md');
    await writeFile(notesFile, `${notes}\n`);
    await $.gh.release.create(tag, { notesFile, target: commit, title: tag });
  } finally {
    await rm(directory, { force: true, recursive: true });
  }
};
import { ensure } from '@zyplux/util/assert';
import { parseJson } from '@zyplux/util/json';

const ReleaseAssetsSchema = z.object({
  data: z.object({
    repository: z.object({
      release: z
        .object({
          isDraft: z.boolean(),
          releaseAssets: z.object({ nodes: z.array(z.object({ name: z.string() })) }),
        })
        .nullable(),
    }),
  }),
});

export const publishReleaseAssets = async (tag: string, notes: string, commit: string, assets: string[]) => {
  const query =
    'query($owner: String!, $name: String!, $tag: String!) { repository(owner: $owner, name: $name) { release(tagName: $tag) { isDraft releaseAssets(first: 100) { nodes { name } } } } }';
  const response = parseJson(
    await readTrimmed($`gh api graphql -F owner={owner} -F name={repo} -f ${`tag=${tag}`} -f ${`query=${query}`}`),
    ReleaseAssetsSchema,
  );
  const release = response.data.repository.release;
  if (release !== null && !release.isDraft) {
    ensure(
      assets.every(asset => release.releaseAssets.nodes.some(node => node.name === path.basename(asset))),
      `published release ${tag} is missing required assets`,
    );
    return;
  }
  const directory = await mkdtemp(path.join(tmpdir(), 'release-assets-'));
  try {
    const notesFile = path.join(directory, 'notes.md');
    await writeFile(notesFile, `${notes}\n`);
    if (release === null)
      await $`gh release create ${tag} --draft --notes-file ${notesFile} --target ${commit} --title ${tag}`;
    await $`gh release upload ${tag} ${assets} --clobber`;
    await $`gh release edit ${tag} --draft=false --notes-file ${notesFile} --target ${commit}`;
  } finally {
    await rm(directory, { force: true, recursive: true });
  }
};
