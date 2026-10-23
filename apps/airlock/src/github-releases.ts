import { $, readTrimmed } from '@zyplux/util/shell';
import { mkdtempDisposable, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import * as z from 'zod';

export const createGithubRelease = async (tag: string, notes: string, commit: string) => {
  await using directory = await mkdtempDisposable(path.join(tmpdir(), 'release-notes-'));
  const notesFile = path.join(directory.path, 'release-notes.md');
  await writeFile(notesFile, `${notes}\n`);
  await $.gh.release.create(tag, { notesFile, target: commit, title: tag });
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

const loadGithubRelease = async (tag: string) => {
  const query =
    'query($owner: String!, $name: String!, $tag: String!) { repository(owner: $owner, name: $name) { release(tagName: $tag) { isDraft releaseAssets(first: 100) { nodes { name } } } } }';
  const response = parseJson(
    await readTrimmed($`gh api graphql -F owner={owner} -F name={repo} -f ${`tag=${tag}`} -f ${`query=${query}`}`),
    ReleaseAssetsSchema,
  );
  return response.data.repository.release;
};

const hasPublishedAssets = (release: Awaited<ReturnType<typeof loadGithubRelease>>, tag: string, assets: string[]) => {
  if (release !== null && !release.isDraft) {
    ensure(
      assets.every(asset => release.releaseAssets.nodes.some(node => node.name === path.basename(asset))),
      `published release ${tag} is missing required assets`,
    );
    return true;
  }
  return false;
};

export const isReleasePublished = async (tag: string, assets: string[]) =>
  hasPublishedAssets(await loadGithubRelease(tag), tag, assets);

export const publishReleaseAssets = async (tag: string, notes: string, commit: string, assets: string[]) => {
  const release = await loadGithubRelease(tag);
  if (hasPublishedAssets(release, tag, assets)) return;
  await using directory = await mkdtempDisposable(path.join(tmpdir(), 'release-assets-'));
  const notesFile = path.join(directory.path, 'notes.md');
  await writeFile(notesFile, `${notes}\n`);
  if (release === null)
    await $`gh release create ${tag} --draft --notes-file ${notesFile} --target ${commit} --title ${tag}`;
  await $`gh release upload ${tag} ${assets} --clobber`;
  await $`gh release edit ${tag} --draft=false --notes-file ${notesFile} --target ${commit}`;
};
