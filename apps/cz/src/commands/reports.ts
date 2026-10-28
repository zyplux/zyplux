import { runPassthrough } from '@zyplux/util/exec';

import type { InferValue } from '#optique';

import { argument, command, constant, message, object, option, optional, string, withDefault } from '#optique';
import { writeWorkspaceGraph } from '#workspace-graph';

const pathArgument = withDefault(argument(string({ metavar: 'PATH' })), '.');

export const workspaceGraphCommand = command(
  'workspace-graph',
  object({ command: constant('workspace-graph' as const), path: pathArgument }),
  { brief: message`Write the pnpm and uv workspace dependency diagram.` },
);
const outOption = optional(option('-o', '--out', string()));
const titleOption = optional(option('--title', string()));

export const statsCommand = command(
  'stats',
  object({ command: constant('stats' as const), out: outOption, path: pathArgument, title: titleOption }),
  { brief: message`Write tracked repository metrics using Clipy.` },
);

export const runWorkspaceGraph = async ({ path }: InferValue<typeof workspaceGraphCommand>) => {
  console.log(`wrote ${await writeWorkspaceGraph(path)}`);
};
export const runStats = async ({ out, path, title }: InferValue<typeof statsCommand>) => {
  await runPassthrough([
    'uv',
    'run',
    'clipy',
    'stats',
    path,
    ...(out === undefined ? [] : ['--out', out]),
    ...(title === undefined ? [] : ['--title', title]),
  ]);
};
