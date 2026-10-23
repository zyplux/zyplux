import { defineProject } from 'vitest/config';

const config = defineProject({
  test: {
    // Package builds share workspace output directories with the util consumer tests.
    sequence: { groupOrder: 1 },
    setupFiles: ['../vitest.setup.ts'],
    testTimeout: 90_000,
  },
});

export default config;
