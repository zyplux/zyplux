import { createRule } from '#create-rule';
import { reportTypeViolations } from '#rule-support/package-type-reports';

export const noTypeOnlyDependencies = createRule({
  create: context => ({
    'Program:exit': () => {
      reportTypeViolations({
        context,
        messageId: 'typeOnlyDependency',
        violationKind: 'typeOnlyDependencies',
      });
    },
  }),
  defaultOptions: [],
  meta: {
    docs: {
      description: 'Disallow type-only dependencies on workspace implementation packages.',
      requiresTypeChecking: true,
    },
    messages: {
      typeOnlyDependency:
        "'{{specifier}}' ({{consumer}} → {{provider}}): implementation package is used only for types; use shared contracts/interfaces or the types accompanying an API this package imports.",
    },
    schema: [],
    type: 'problem',
  },
  name: 'no-type-only-dependencies',
});
