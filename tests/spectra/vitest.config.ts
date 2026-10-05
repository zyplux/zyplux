import { defineProject } from 'vitest/config';

const config = defineProject({
  test: { name: 'spectra', setupFiles: ['./stories/fakes/readline-mock.ts'], testTimeout: 30_000 },
});

export default config;
