import { command, constant, message, object } from '@optique/core';

import { loadPreparedReleases } from '#release-notes';

export const checkReleaseNotesCommand = command(
  'check-release-notes',
  object({ command: constant('check-release-notes' as const) }),
  {
    aliases: ['check'],
    brief: message`Validate prepared change intents, synchronized versions and non-empty release notes.`,
  },
);

export const runCheckReleaseNotes = async () => {
  await loadPreparedReleases();
};
