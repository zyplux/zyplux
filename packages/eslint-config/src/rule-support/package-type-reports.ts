import type { RuleContext } from '@typescript-eslint/utils/ts-eslint';
import type ts from 'typescript';

import { ESLintUtils } from '@typescript-eslint/utils';
import { scanTypeDependencies } from '@zyplux/util/type-dependencies';
import { listWorkspacePackages } from '@zyplux/util/workspace-architecture';

type TypeViolations = ReturnType<typeof scanTypeDependencies>;

const cache = new WeakMap<ts.Program, TypeViolations>();

const loadTypeViolations = (program: ts.Program, root: string) => {
  const cached = cache.get(program);
  if (cached !== undefined) return cached;
  const violations = scanTypeDependencies({
    packages: listWorkspacePackages(root),
    program,
    sharedTypeSurfaces: new Set(['contracts', 'interfaces']),
  });
  cache.set(program, violations);
  return violations;
};

type TypeReport<MessageId extends string> = {
  context: RuleContext<MessageId, readonly unknown[]>;
  messageId: MessageId;
  violationKind: keyof TypeViolations;
};

export const reportTypeViolations = <MessageId extends string>({
  context,
  messageId,
  violationKind,
}: TypeReport<MessageId>) => {
  const { program } = ESLintUtils.getParserServices(context);
  const configuredRoot = context.languageOptions.parserOptions.tsconfigRootDir;
  const root = typeof configuredRoot === 'string' ? configuredRoot : context.cwd;
  const violations = loadTypeViolations(program, root)[violationKind];
  for (const { consumer, filePath, line, provider, specifier } of violations) {
    if (filePath !== context.filename) continue;
    context.report({
      data: { consumer: consumer.name, provider: provider.name, specifier },
      loc: { end: { column: 1, line }, start: { column: 0, line } },
      messageId,
    });
  }
};
