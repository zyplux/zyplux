import { plugin, zyplux } from '@zyplux/eslint-config';
import { libraryTest } from '@zyplux/spectra/library-test-api';
import { Linter } from 'eslint';
import path from 'node:path';
import ts from 'typescript';
import tseslint from 'typescript-eslint';

type ArchitectureFixtures = {
  lintArchitecture: (
    files: Record<string, string>,
    rule?: string | string[],
    options?: unknown[],
    filename?: string,
  ) => Promise<Linter.LintMessage[]>;
  lintArchitectureScopes: (
    files: Record<string, string>,
    rule: string,
    filename: string,
  ) => Promise<Linter.LintMessage[]>;
};

export const test = libraryTest.extend<ArchitectureFixtures>({
  lintArchitecture: async ({ tempDir }, use) => {
    await use(
      async (files, rule = 'use-package-type-exports', options = [], filename = 'packages/consumer/src/entry.ts') => {
        for (const [file, content] of Object.entries(files)) await tempDir.write(file, content);
        const config = ts.parseJsonConfigFileContent(
          {
            compilerOptions: {
              paths: {
                '#private': ['./packages/provider/src/private.ts'],
                '@provider/*': ['./packages/provider/src/*'],
                '@sample/consumer/*': ['./packages/consumer/src/*'],
                '@sample/provider': ['./packages/provider/src/api.ts'],
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
            rules: Object.fromEntries(
              (Array.isArray(rule) ? rule : [rule]).map(name => [`@zyplux/${name}`, ['error', ...options]]),
            ),
          },
          file,
        );
      },
    );
  },
  lintArchitectureScopes: async ({ tempDir }, use) => {
    await use(async (files, rule, filename) => {
      for (const [file, content] of Object.entries(files)) await tempDir.write(file, content);
      const configs = zyplux({ tsconfigRootDir: tempDir.path }).flatMap(config => {
        const setting = config.rules?.[`@zyplux/${rule}`];
        return setting === undefined
          ? []
          : {
              ...(config.files !== undefined && { files: config.files }),
              plugins: { '@zyplux': plugin },
              rules: { [`@zyplux/${rule}`]: setting },
            };
      });
      const linter = new Linter({ cwd: tempDir.path });
      return linter.verify(
        files[filename] ?? '',
        [{ files: ['**/*.{js,jsx,mjs,cjs,ts,tsx,mts,cts}'], languageOptions: { parser: tseslint.parser } }, ...configs],
        path.join(tempDir.path, filename),
      );
    });
  },
});
export { describe, expect } from 'vitest';
