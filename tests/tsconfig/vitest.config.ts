import { defineProject } from 'vitest/config';

const config = defineProject({
  test: {
    setupFiles: ['../vitest.setup.ts'],
  },
});

export default config;
