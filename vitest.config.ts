import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    projects: ['packages/eslint-config', 'tests/eslint-config', 'tests/cz'],
  },
});
