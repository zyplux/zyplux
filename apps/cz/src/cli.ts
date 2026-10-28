import { loadPackageVersion } from '@zyplux/util/manifest';

import { chunkFilesCommand, runChunkFiles } from './commands/chunk-files.ts';
import { cleanCommand, runClean } from './commands/clean.ts';
import { cloneReferenceRepoCommand, runCloneReferenceRepo } from './commands/clone-reference-repo.ts';
import { depsCatalogCommand, runDepsCatalog } from './commands/deps-catalog.ts';
import { lintMermaidCommand, runLintMermaid } from './commands/lint-mermaid.ts';
import { pushBranchCommand, runPushBranch } from './commands/push-branch.ts';
import { runStats, runWorkspaceGraph, statsCommand, workspaceGraphCommand } from './commands/reports.ts';
import { runUpgrade, upgradeCommand } from './commands/upgrade.ts';
import { defineProgram, message, or, run } from './optique.ts';

const VERSION = loadPackageVersion(import.meta.url);

const program = defineProgram({
  metadata: {
    brief: message`Repo automation.`,
    name: 'cz',
    version: VERSION,
  },
  parser: or(
    chunkFilesCommand,
    statsCommand,
    workspaceGraphCommand,
    pushBranchCommand,
    cloneReferenceRepoCommand,
    depsCatalogCommand,
    lintMermaidCommand,
    cleanCommand,
    upgradeCommand,
  ),
});

type CzIo = {
  onExit?: (exitCode: number) => never;
  stderr?: (line: string) => void;
  stdout?: (line: string) => void;
};

export const runCz = async (args: readonly string[], io: CzIo = {}) => {
  const result = run(program, {
    aboveError: 'usage',
    args,
    completion: 'both',
    help: 'both',
    showDefault: true,
    version: VERSION,
    ...io,
  });

  switch (result.command) {
    case 'chunk-files': {
      return runChunkFiles(result);
    }
    case 'clean': {
      return runClean(result);
    }
    case 'clone-reference-repo': {
      return runCloneReferenceRepo(result);
    }
    case 'deps-catalog': {
      return runDepsCatalog(result);
    }
    case 'lint-mermaid': {
      return runLintMermaid();
    }
    case 'push-branch': {
      return runPushBranch(result);
    }
    case 'stats': {
      return runStats(result);
    }
    case 'upgrade': {
      return runUpgrade(result);
    }
    case 'workspace-graph': {
      return runWorkspaceGraph(result);
    }
  }
};
