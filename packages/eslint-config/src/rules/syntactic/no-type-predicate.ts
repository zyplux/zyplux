import { createRule } from '#create-rule';

export const noTypePredicate = createRule({
  create: context => ({
    TSTypePredicate: node => {
      if (node.asserts) return;
      context.report({
        messageId: 'noTypePredicate',
        node,
      });
    },
  }),
  meta: {
    docs: {
      description:
        'Disallow user-defined type guards (`x is T`); prefer a real zod schema (`z.object` / `z.discriminatedUnion` etc., not `z.custom<T>`) or manual narrowing via runtime checks and restructuring.',
    },
    messages: {
      noTypePredicate:
        'User-defined type guards (`x is T`) are not allowed. Prefer a real zod schema (`z.object` / `z.discriminatedUnion`, not `z.custom<T>`) that returns the typed value, or manual narrowing via `typeof`/`in` checks and restructuring.',
    },
    schema: [],
    type: 'problem',
  },
  name: 'no-type-predicate',
});
