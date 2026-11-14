import { defineProject } from 'vitest/config';

const config = defineProject({
  test: { name: 'spectra', setupFiles: ['./fakes/readline-mock.ts'], testTimeout: 30_000 },
});

export default config;
