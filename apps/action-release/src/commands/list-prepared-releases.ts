import { command, constant, message, object } from '@optique/core';

import { loadPreparedReleases } from '#release-notes';

export const listPreparedReleasesCommand = command(
  'list-prepared-releases',
  object({ command: constant('list-prepared-releases' as const) }),
  {
    aliases: ['notes'],
    brief: message`Print validated release kinds, labels, versions, tags and changelog entries as JSON.`,
  },
);

export const runListPreparedReleases = async () => {
  console.log(JSON.stringify(await loadPreparedReleases()));
};
