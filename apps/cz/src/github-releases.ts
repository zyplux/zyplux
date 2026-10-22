import { $ } from '@zyplux/util/shell';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

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
