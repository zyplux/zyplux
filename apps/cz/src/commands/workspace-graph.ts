import type { InferValue } from '#optique';

import { argument, command, constant, message, object, string, withDefault } from '#optique';
import { writeWorkspaceGraph } from '#workspace-graph';

const pathArgument = withDefault(argument(string({ metavar: 'PATH' })), '.');

export const workspaceGraphCommand = command(
  'workspace-graph',
  object({
    command: constant('workspace-graph' as const),
    path: pathArgument,
  }),
  { brief: message`Write the pnpm and uv workspace dependency diagram.` },
);

export const runWorkspaceGraph = async ({ path }: InferValue<typeof workspaceGraphCommand>) => {
  console.log(`wrote ${await writeWorkspaceGraph(path)}`);
};
