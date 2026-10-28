import { run } from '@zyplux/util/exec';
import { parseJson } from '@zyplux/util/json';
import { $, readTrimmed } from '@zyplux/util/shell';

import { SourceSnapshotSchema } from './contracts.ts';

export const loadSourceSnapshot = async (directory: string) => {
  const root = await readTrimmed($.git.showToplevel(directory));
  const json = await run(['uv', 'run', '--no-sync', 'cerberus', 'source-oracle', root]).cwd(root).quiet().text();
  return { files: parseJson(json, SourceSnapshotSchema), root };
};
