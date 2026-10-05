import { defineProject } from 'vitest/config';

const config = defineProject({
  test: {
    setupFiles: ['../vitest.setup.ts'],
    testTimeout: 90_000,
  },
});

export default config;
