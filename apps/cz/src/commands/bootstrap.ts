import type { InferValue } from '@optique/core/parser';

import { object } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { argument, command, constant } from '@optique/core/primitives';
import { string } from '@optique/core/valueparser';
import { ensure } from '@zyplux/util';
import { $ } from '@zyplux/util/shell';

import { loadReleaseTargets } from '#release-targets';

const labelArgument = argument(string({ metavar: 'LABEL' }), {
  description: message`npm target label to first-publish, e.g. @zyplux/util.`,
});

export const bootstrapCommand = command(
  'bootstrap',
  object({ command: constant('bootstrap' as const), label: labelArgument }),
  {
    brief: message`First-publish a new npm target with a token so trusted publishing can be enabled afterward.`,
  },
);

type BootstrapConfig = InferValue<typeof bootstrapCommand>;

export const runBootstrap = async ({ label }: BootstrapConfig) => {
  const targets = await loadReleaseTargets();
  const target = targets.find(candidate => candidate.label === label);
  ensure(target !== undefined, `no release target labeled '${label}' in release-targets.toml`);
  ensure(target.kind === 'npm', `bootstrap is npm-only; '${label}' is a ${target.kind} target`);

  const version = await target.readVersion();
  if (await target.isPublished(version)) {
    console.log(`${label} ${version} is already on npm — enable its trusted publisher; no bootstrap needed`);
    return;
  }

  console.log(`Bootstrapping ${label} ${version} to npm ...`);
  await $`cd ${target.dir} && bun pm pack && bunx npm@latest publish ./*.tgz --access public`;
  console.log(
    `Published ${label} ${version}. Enable its trusted publisher on npmjs.com; later releases publish via OIDC.`,
  );
};
