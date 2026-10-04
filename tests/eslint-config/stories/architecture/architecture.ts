import { plugin } from '@zyplux/eslint-config';
import { libraryTest } from '@zyplux/spectra/library-test-api';
import { Linter } from 'eslint';
import path from 'node:path';
import ts from 'typescript';
import tseslint from 'typescript-eslint';

type ArchitectureFixtures = {
  lintArchitecture: (
    files: Record<string, string>,
    rule?: string,
    options?: unknown[],
    filename?: string,
  ) => Promise<Linter.LintMessage[]>;
};

export const test = libraryTest.extend<ArchitectureFixtures>({
  lintArchitecture: async ({ tempDir }, use) => {
    await use(async (files, rule = 'package-imports', options = [], filename = 'packages/consumer/src/entry.ts') => {
      for (const [file, content] of Object.entries(files)) await tempDir.write(file, content);
      const config = ts.parseJsonConfigFileContent(
        {
          compilerOptions: {
            paths: {
              '@provider/*': ['./packages/provider/src/*'],
              '@sample/consumer/*': ['./packages/consumer/src/*'],
              '@sample/provider/*': ['./packages/provider/src/*'],
            },
            strict: true,
          },
          include: ['**/*.ts'],
        },
        ts.sys,
        tempDir.path,
      );
      const program = ts.createProgram(config.fileNames, config.options);
      const linter = new Linter({ cwd: tempDir.path });
      const file = path.join(tempDir.path, filename);
      return linter.verify(
        files[filename] ?? '',
        {
          files: ['**/*.ts'],
          languageOptions: {
            parser: tseslint.parser,
            parserOptions: { programs: [program], tsconfigRootDir: tempDir.path },
          },
          plugins: { '@zyplux': plugin },
          rules: { [`@zyplux/${rule}`]: ['error', ...options] },
        },
        file,
      );
    });
  },
});
export { describe, expect } from 'vitest';
