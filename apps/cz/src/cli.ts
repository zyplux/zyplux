import { loadPackageVersion } from '@zyplux/util/manifest';

import { assertTagVersionCommand, runAssertTagVersion } from './commands/assert-tag-version.ts';
import { bootstrapNpmTargetCommand, runBootstrapNpmTarget } from './commands/bootstrap-npm-target.ts';
import { cleanCommand, runClean } from './commands/clean.ts';
import { cloneReferenceRepoCommand, runCloneReferenceRepo } from './commands/clone-reference-repo.ts';
import { depsCatalogCommand, runDepsCatalog } from './commands/deps-catalog.ts';
import { printTagKindCommand, runPrintTagKind } from './commands/print-tag-kind.ts';
import { publishTaggedTargetCommand, runPublishTaggedTarget } from './commands/publish-tagged-target.ts';
import { pushBranchCommand, runPushBranch } from './commands/push-branch.ts';
import { releaseBumpedTargetsCommand, runReleaseBumpedTargets } from './commands/release-bumped-targets.ts';
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
    pushBranchCommand,
    cloneReferenceRepoCommand,
    depsCatalogCommand,
    releaseBumpedTargetsCommand,
    assertTagVersionCommand,
    bootstrapNpmTargetCommand,
    publishTaggedTargetCommand,
    printTagKindCommand,
    cleanCommand,
    upgradeCommand,
  ),
});

type CzIo = {
  onExit?: (exitCode: number) => never;
  stderr?: (line: string) => void;
  stdout?: (line: string) => void;
};

const assertNever = (value: never) => {
  throw new Error(`unhandled command: ${JSON.stringify(value)}`);
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
    case 'assert-tag-version': {
      return runAssertTagVersion(result);
    }
    case 'bootstrap-npm-target': {
      return runBootstrapNpmTarget(result);
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
    case 'print-tag-kind': {
      return runPrintTagKind(result);
    }
    case 'publish-tagged-target': {
      return runPublishTaggedTarget(result);
    }
    case 'push-branch': {
      return runPushBranch(result);
    }
    case 'release-bumped-targets': {
      return runReleaseBumpedTargets();
    }
    case 'upgrade': {
      return runUpgrade(result);
    }
    default: {
      return assertNever(result);
    }
  }
};
