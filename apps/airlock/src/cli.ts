import type { InferValue } from '@optique/core';

import { message, or } from '@optique/core';
import { defineProgram } from '@optique/core/program';
import { run } from '@optique/run';
import { loadPackageVersion } from '@zyplux/util/manifest';

import { assertTagVersionCommand, runAssertTagVersion } from './commands/assert-tag-version.ts';
import { bootstrapNpmTargetCommand, runBootstrapNpmTarget } from './commands/bootstrap-npm-target.ts';
import { checkReleaseNotesCommand, runCheckReleaseNotes } from './commands/check-release-notes.ts';
import { checkSurfaceCommand, runCheckSurface } from './commands/check-surface.ts';
import { listPreparedReleasesCommand, runListPreparedReleases } from './commands/list-prepared-releases.ts';
import { planCommand, runPlan } from './commands/plan.ts';
import { prepareReleaseCommand, runPrepareRelease } from './commands/prepare-release.ts';
import { printTagKindCommand, runPrintTagKind } from './commands/print-tag-kind.ts';
import { publishBatchCommand, runPublishBatch } from './commands/publish-batch.ts';
import { publishNpmCommand, runPublishNpm } from './commands/publish-npm.ts';
import { publishTaggedTargetCommand, runPublishTaggedTarget } from './commands/publish-tagged-target.ts';

const airlockCommand = or(
  assertTagVersionCommand,
  bootstrapNpmTargetCommand,
  checkReleaseNotesCommand,
  checkSurfaceCommand,
  listPreparedReleasesCommand,
  prepareReleaseCommand,
  planCommand,
  printTagKindCommand,
  publishBatchCommand,
  publishNpmCommand,
  publishTaggedTargetCommand,
);

const runAirlockCommand = async (config: InferValue<typeof airlockCommand>) => {
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
    case 'check-surface': {
      return runCheckSurface(config);
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
    case 'publish-batch': {
      return runPublishBatch(config);
    }
    case 'publish-npm': {
      return runPublishNpm();
    }
    case 'publish-tagged-target': {
      return runPublishTaggedTarget(config);
    }
  }
};

const VERSION = loadPackageVersion(import.meta.url);
const program = defineProgram({
  metadata: {
    brief: message`Prepare and publish reviewed workspace releases.`,
    name: 'airlock',
    version: VERSION,
  },
  parser: airlockCommand,
});

type AirlockIo = {
  onExit?: (exitCode: number) => never;
  stderr?: (line: string) => void;
  stdout?: (line: string) => void;
};

export const runAirlock = async (args: readonly string[], io: AirlockIo = {}) =>
  runAirlockCommand(
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
