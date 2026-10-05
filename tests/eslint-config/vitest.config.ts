import { defineProject } from 'vitest/config';

const config = defineProject({
  test: {
    testTimeout: 30_000,
  },
});

export default config;
