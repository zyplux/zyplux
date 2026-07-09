import type { Message } from '@optique/core/message';

import { object } from '@optique/core/constructs';
import { argument, command, constant } from '@optique/core/primitives';
import { string } from '@optique/core/valueparser';

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
