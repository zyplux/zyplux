import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const workspaceRoot = fileURLToPath(new URL('../../../', import.meta.url));

const NESTED_REPO_MANIFESTS = { 'service-a': 'package.json', 'service-b': 'pyproject.toml' } as const;

export const createNestedGitRepos = async (reposRoot: string) => {
  const manifestPaths: string[] = [];
  for (const [repoName, manifestName] of Object.entries(NESTED_REPO_MANIFESTS)) {
    const repoDir = path.join(reposRoot, repoName);
    await mkdir(repoDir, { recursive: true });
    execFileSync('git', ['init', '--quiet'], { cwd: repoDir, stdio: 'ignore' });
    await writeFile(path.join(repoDir, manifestName), '{}');
    execFileSync('git', ['add', manifestName], { cwd: repoDir, stdio: 'ignore' });
    manifestPaths.push(path.join(repoDir, manifestName));
  }
  return manifestPaths;
};
