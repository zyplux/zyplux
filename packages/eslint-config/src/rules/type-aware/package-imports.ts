import { ESLintUtils } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

import { getTypeViolations } from './type-ownership.ts';

export const packageImports = createRule({
  create: context => {
    const services = ESLintUtils.getParserServices(context);
    const configuredRoot = context.languageOptions.parserOptions.tsconfigRootDir;
    const root = typeof configuredRoot === 'string' ? configuredRoot : context.cwd;
    return {
      'Program:exit': () => {
        for (const message of getTypeViolations(services, root)) {
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
      description: 'Enforce cross-package type ownership.',
      requiresTypeChecking: true,
    },
    messages: { ownership: '{{message}}' },
    schema: [],
    type: 'problem',
  },
  name: 'package-imports',
});
