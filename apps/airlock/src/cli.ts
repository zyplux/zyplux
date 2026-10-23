import type { InferValue } from '@optique/core';

import { message, or } from '@optique/core';
import { defineProgram } from '@optique/core/program';
import { run } from '@optique/run';
import { loadPackageVersion } from '@zyplux/util/manifest';

import { assertTagVersionCommand, runAssertTagVersion } from './commands/assert-tag-version.ts';
import { bootstrapNpmTargetCommand, runBootstrapNpmTarget } from './commands/bootstrap-npm-target.ts';
import { checkReleaseNotesCommand, runCheckReleaseNotes } from './commands/check-release-notes.ts';
import { listPreparedReleasesCommand, runListPreparedReleases } from './commands/list-prepared-releases.ts';
import { planCommand, runPlan } from './commands/plan.ts';
import { prepareReleaseCommand, runPrepareRelease } from './commands/prepare-release.ts';
import { printTagKindCommand, runPrintTagKind } from './commands/print-tag-kind.ts';
import { publishNpmCommand, runPublishNpm } from './commands/publish-npm.ts';
import { publishTaggedTargetCommand, runPublishTaggedTarget } from './commands/publish-tagged-target.ts';
import { releaseBumpedTargetsCommand, runReleaseBumpedTargets } from './commands/release-bumped-targets.ts';

export const releaseCommand = or(
  assertTagVersionCommand,
  bootstrapNpmTargetCommand,
  checkReleaseNotesCommand,
  listPreparedReleasesCommand,
  prepareReleaseCommand,
  planCommand,
  printTagKindCommand,
  publishNpmCommand,
  publishTaggedTargetCommand,
  releaseBumpedTargetsCommand,
);

export const runReleaseCommand = async (config: InferValue<typeof releaseCommand>) => {
  switch (config.command) {
    case 'assert-tag-version': {
      return runAssertTagVersion(config);
    }
    case 'bootstrap-npm-target': {
      return runBootstrapNpmTarget(config);
    }
    case 'check-release-notes': {
      return runCheckReleaseNotes();
    }
    case 'list-prepared-releases': {
      return runListPreparedReleases();
    }
    case 'plan': {
      return runPlan(config);
    }
    case 'prepare-release': {
      return runPrepareRelease();
    }
    case 'print-tag-kind': {
      return runPrintTagKind(config);
    }
    case 'publish-npm': {
      return runPublishNpm();
    }
    case 'publish-tagged-target': {
      return runPublishTaggedTarget(config);
    }
    case 'release-bumped-targets': {
      return runReleaseBumpedTargets(config);
    }
  }
};

const VERSION = loadPackageVersion(import.meta.url);
const program = defineProgram({
  metadata: {
    brief: message`Prepare and publish reviewed workspace releases.`,
    name: 'zyplux-release',
    version: VERSION,
  },
  parser: releaseCommand,
});

type ReleaseIo = {
  onExit?: (exitCode: number) => never;
  stderr?: (line: string) => void;
  stdout?: (line: string) => void;
};

export const runRelease = async (args: readonly string[], io: ReleaseIo = {}) =>
  runReleaseCommand(
    run(program, {
      aboveError: 'usage',
      args,
      completion: 'both',
      help: 'both',
      showDefault: true,
      version: VERSION,
      ...io,
    }),
  );
