#!/usr/bin/env bun
import { or } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { defineProgram } from '@optique/core/program';
import { run } from '@optique/run';

import { applyRulesetCommand, runApplyRuleset } from '#commands/apply-ruleset';
import { assertTagCommand, runAssertTag } from '#commands/assert-tag';
import { bootstrapCommand, runBootstrap } from '#commands/bootstrap';
import { cloneCommand, runClone } from '#commands/clone';
import { pushCommand, runPush } from '#commands/push';
import { releaseCommand, runRelease } from '#commands/release';

const VERSION = '0.0.0';

const program = defineProgram({
  metadata: {
    brief: message`Repo automation for zyp-cerberus.`,
    name: 'cz',
    version: VERSION,
  },
  parser: or(pushCommand, cloneCommand, releaseCommand, assertTagCommand, bootstrapCommand, applyRulesetCommand),
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
    case 'apply-ruleset': {
      return runApplyRuleset();
    }
    case 'assert-tag': {
      return runAssertTag(result);
    }
    case 'bootstrap': {
      return runBootstrap(result);
    }
    case 'clone': {
      return runClone(result);
    }
    case 'push': {
      return runPush(result);
    }
    case 'release': {
      return runRelease();
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
