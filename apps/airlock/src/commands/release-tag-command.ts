import type { Message } from '@optique/core';

import { argument, command, constant, object, string } from '@optique/core';

type ReleaseTagCommandSpec = {
  alias: string;
  brief: Message;
  tagDescription: Message;
};

export const makeReleaseTagCommand = <const Name extends string>(
  name: Name,
  { alias, brief, tagDescription }: ReleaseTagCommandSpec,
) => {
  const tag = argument(string({ metavar: 'TAG' }), { description: tagDescription });
  return command(name, object({ command: constant(name), tag }), { aliases: [alias], brief });
};
