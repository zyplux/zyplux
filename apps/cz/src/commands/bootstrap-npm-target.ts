import { ensure } from '@zyplux/util/assert';

import type { InferValue } from '#optique';

import { argument, command, constant, message, object, string } from '#optique';
import { loadReleaseTargets } from '#release-targets';

import { publishNpm } from './publish-tagged-target.ts';

const labelArgument = argument(string({ metavar: 'LABEL' }), {
  description: message`npm target label to first-publish, e.g. @zyplux/util.`,
});

export const bootstrapNpmTargetCommand = command(
  'bootstrap-npm-target',
  object({ command: constant('bootstrap-npm-target' as const), label: labelArgument }),
  {
    aliases: ['bn'],
    brief: message`First-publish a new npm target using local registry authentication.`,
  },
);

type BootstrapNpmTargetConfig = InferValue<typeof bootstrapNpmTargetCommand>;

export const runBootstrapNpmTarget = async ({ label }: BootstrapNpmTargetConfig) => {
  const targets = await loadReleaseTargets();
  const target = targets.find(candidate => candidate.label === label);
  ensure(target !== undefined, `no release target labeled '${label}' in release-targets.toml`);
  ensure(target.kind === 'npm', `bootstrap is npm-only; '${label}' is a ${target.kind} target`);

  const version = await target.readVersion();
  if (await target.isPublished(version)) {
    console.log(`${label} ${version} is already published; no bootstrap needed`);
    return;
  }

  console.log(`Bootstrapping ${label} ${version} to npm ...`);
  await publishNpm(target.dir);
  console.log(`Published ${label} ${version}. Configure registry authentication in the release workflow.`);
};
