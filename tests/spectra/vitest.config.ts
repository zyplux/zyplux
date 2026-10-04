import { defineProject } from 'vitest/config';

export default defineProject({
  test: { name: 'spectra', setupFiles: ['./stories/fakes/readline-mock.ts'], testTimeout: 30_000 },
});
