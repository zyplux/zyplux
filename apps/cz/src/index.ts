#!/usr/bin/env bun
import { or } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { defineProgram } from '@optique/core/program';
import { run } from '@optique/run';

import { applyOrgRulesetsCommand, runApplyOrgRulesets } from '#commands/apply-org-rulesets';
import { assertTagVersionCommand, runAssertTagVersion } from '#commands/assert-tag-version';
import { bootstrapNpmTargetCommand, runBootstrapNpmTarget } from '#commands/bootstrap-npm-target';
import { cloneReferenceRepoCommand, runCloneReferenceRepo } from '#commands/clone-reference-repo';
import { depsCatalogCommand, runDepsCatalog } from '#commands/deps-catalog';
import { printTagKindCommand, runPrintTagKind } from '#commands/print-tag-kind';
import { publishTaggedTargetCommand, runPublishTaggedTarget } from '#commands/publish-tagged-target';
import { pushBranchCommand, runPushBranch } from '#commands/push-branch';
import { releaseBumpedTargetsCommand, runReleaseBumpedTargets } from '#commands/release-bumped-targets';
import pkg from '#package.json' with { type: 'json' };

const VERSION = pkg.version;

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
    applyOrgRulesetsCommand,
    publishTaggedTargetCommand,
    printTagKindCommand,
  ),
});

const assertNever = (value: never) => {
  throw new Error(`unhandled command: ${JSON.stringify(value)}`);
};

const main = async () => {
  const result = run(program, {
    aboveError: 'usage',
    completion: 'both',
    help: 'both',
    showDefault: true,
    version: VERSION,
  });

  switch (result.command) {
    case 'apply-org-rulesets': {
      return runApplyOrgRulesets();
    }
    case 'assert-tag-version': {
      return runAssertTagVersion(result);
    }
    case 'bootstrap-npm-target': {
      return runBootstrapNpmTarget(result);
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
    default: {
      return assertNever(result);
    }
  }
};

try {
  await main();
} catch (error) {
  console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
