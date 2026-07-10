import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

export type TempDir = {
  exists: (relativePath: string) => boolean;
  path: string;
  remove: () => Promise<void>;
  write: (relativePath: string, content: string) => Promise<string>;
};

export const createTempDir = async (prefix = 'zyplux-test-'): Promise<TempDir> => {
  const dir = await mkdtemp(path.join(tmpdir(), prefix));

  return {
    exists: relativePath => existsSync(path.join(dir, relativePath)),
    path: dir,
    remove: () => rm(dir, { force: true, recursive: true }),
    write: async (relativePath, content) => {
      const filePath = path.join(dir, relativePath);
      await mkdir(path.dirname(filePath), { recursive: true });
      await writeFile(filePath, content, 'utf8');
      return filePath;
    },
  };
};
