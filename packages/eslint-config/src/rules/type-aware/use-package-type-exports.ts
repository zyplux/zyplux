import { createRule } from '#create-rule';
import { reportTypeViolations } from '#rule-support/package-type-reports';

export const usePackageTypeExports = createRule({
  create: context => ({
    'Program:exit': () => {
      reportTypeViolations({
        context,
        messageId: 'packageExport',
        violationKind: 'unexportedTypes',
      });
    },
  }),
  defaultOptions: [],
  meta: {
    docs: {
      description: 'Require cross-package type references to use public package exports.',
      requiresTypeChecking: true,
    },
    messages: {
      packageExport:
        "'{{specifier}}' ({{consumer}} → {{provider}}) is not a public package entry; cross-package types must use the provider's package.json exports.",
    },
    schema: [],
    type: 'problem',
  },
  name: 'use-package-type-exports',
});
