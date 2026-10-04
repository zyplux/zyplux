import { ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

import { findImportViolation, getWorkspacePolicy } from './workspace-policy.ts';

export const packageImports = createRule({
  create: context => {
    const services = ESLintUtils.getParserServices(context);
    const configuredRoot = context.languageOptions.parserOptions.tsconfigRootDir;
    const root = typeof configuredRoot === 'string' ? configuredRoot : context.cwd;
    return {
      'Program:exit': () => {
        const policy = getWorkspacePolicy(services, root);
        for (const reference of policy.imports) {
          if (reference.filePath !== context.filename) continue;
          const message = findImportViolation(reference.specifier, reference.filePath, services, root);
          if (message !== undefined)
            context.report({
              data: { message },
              loc: { end: { column: 1, line: reference.line }, start: { column: 0, line: reference.line } },
              messageId: 'ownership',
            });
        }
        for (const message of policy.violations) {
          if (!message.startsWith(`${context.filename}:`)) continue;
          const line = Number(message.slice(context.filename.length + 1).split(' ', 1)[0]);
          context.report({
            data: { message },
            loc: { end: { column: 1, line }, start: { column: 0, line } },
            messageId: 'ownership',
          });
        }
      },
    };
  },
  defaultOptions: [],
  meta: {
    docs: {
      description: 'Enforce declared dependency direction and cross-package type ownership.',
      requiresTypeChecking: true,
    },
    messages: { ownership: '{{message}}' },
    schema: [],
    type: 'problem',
  },
  name: 'package-imports',
});
