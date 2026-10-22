import { command, constant, message, object } from '#optique';
import { loadPreparedReleases } from '#release-notes';

export const checkReleaseNotesCommand = command(
  'check-release-notes',
  object({ command: constant('check-release-notes' as const) }),
  {
    brief: message`Validate consumed Changesets, synchronized versions and non-empty release notes.`,
  },
);

export const runCheckReleaseNotes = async () => {
  await loadPreparedReleases();
};
