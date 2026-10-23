import { ensure } from '@zyplux/util/assert';
import { $, readTrimmed } from '@zyplux/util/shell';
import { Parser } from 'commonmark';
import { glob, readFile } from 'node:fs/promises';
import path from 'node:path';

import { validatePythonVersions } from './python-releases.ts';
import { loadReleaseTargets } from './release-targets.ts';

type ChangelogHeading = { end: number; name: string; start: number };

const VERSION_HEADING_LEVEL = 2;

const findReleaseSection = (markdown: string, version: string) => {
  const lines = markdown.split('\n');
  const headings: ChangelogHeading[] = [];
  const document = new Parser().parse(markdown);
  for (let node = document.firstChild; node !== null; node = node.next) {
    if (node.type === 'heading' && node.level <= VERSION_HEADING_LEVEL) {
      headings.push({
        end: node.sourcepos[1][0],
        name: lines[node.sourcepos[0][0] - 1] ?? '',
        start: node.sourcepos[0][0] - 1,
      });
    }
  }
  const section = headings.find(heading => heading.name === `## ${version}`);
  ensure(section !== undefined, `no release notes for ${version}; run pnpm release:prepare`);
  const next = headings.find(heading => heading.start > section.start);
  return lines.slice(section.end, next?.start).join('\n').trim();
};

const hasReleaseEntries = (notes: string) => {
  const document = new Parser().parse(notes);
  for (let node = document.firstChild; node !== null; node = node.next) {
    if (node.type === 'list' && node.firstChild?.firstChild) return true;
  }
  return false;
};

export const loadReleaseNotes = async (directory: string, version: string) => {
  const changelog = path.join(directory, 'CHANGELOG.md');
  const notes = findReleaseSection(await readFile(changelog, 'utf8'), version);
  ensure(hasReleaseEntries(notes), `${changelog}: release ${version} has no changelog entries`);
  return notes;
};

export const validateConsumedIntents = async () => {
  const root = await readTrimmed($.git.showToplevel());
  const pending = await Array.fromAsync(glob('.changeset/*.md', { cwd: root, exclude: ['.changeset/README.md'] }));
  ensure(pending.length === 0, `Unconsumed change intents: ${pending.join(', ')}; run pnpm release:prepare`);
};

export const loadPreparedReleases = async () => {
  await validateConsumedIntents();
  const targets = await loadReleaseTargets();
  await validatePythonVersions(targets);
  return Promise.all(
    targets.map(async ({ dir, kind, label, tag, version }) => ({
      kind,
      label,
      notes: await loadReleaseNotes(dir, version),
      tag,
      version,
    })),
  );
};
