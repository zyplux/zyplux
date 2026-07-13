import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES } from '@typescript-eslint/utils';

import { createRule } from '#create-rule';

type MessageId = 'subjectOutsideRole';
type Options = [{ subject: string }];

const CONTRACTS_SUFFIX = '/contracts';

export const fixtureRoleImports = createRule<Options, MessageId>({
  create: (context, [{ subject }]) => {
    const isSubjectSpecifier = (specifier: string) =>
      (specifier === subject || specifier.startsWith(`${subject}/`)) && specifier !== `${subject}${CONTRACTS_SUFFIX}`;

    const reportsSubject = (source: null | TSESTree.StringLiteral) => {
      if (source !== null && isSubjectSpecifier(source.value)) {
        context.report({ messageId: 'subjectOutsideRole', node: source });
      }
    };

    return {
      ExportAllDeclaration: node => {
        reportsSubject(node.source);
      },
      ExportNamedDeclaration: node => {
        reportsSubject(node.source);
      },
      ImportDeclaration: node => {
        reportsSubject(node.source);
      },
      ImportExpression: node => {
        const { source } = node;
        if (source.type === AST_NODE_TYPES.Literal && typeof source.value === 'string') {
          reportsSubject(source);
        }
      },
    };
  },
  defaultOptions: [{ subject: '' }],
  meta: {
    docs: {
      description:
        "Keep a torn-out test suite's subject package behind its arrange/act fixtures: only fixtures/arrange.ts and fixtures/act.ts may import the subject (world-building and driving are both legitimate reasons to reach it), every other module under fixtures/ is reported, and the subject's `/contracts` seam stays importable from any role module since it carries no behavior. The subject package name comes from the `subject` option, resolved once per suite by the shipped `zyplux()` config: it pairs each `tests/<basename>` suite with the workspace member directory of the same basename outside `tests/` (`tests/util-ts` pairs with `packages/util-ts`, whatever that package calls itself) and reads the subject's name from that member's own package.json. In-editor complement of the cerberus `fixture_roles_ts` bite, which now only pins the suite's manifest shape (`#fixtures` targets fixtures/index.ts, fixtures/act.ts is present).",
    },
    messages: {
      subjectOutsideRole:
        "Only fixtures/arrange.ts and fixtures/act.ts import the suite's subject package — move this import there, or reach the subject's /contracts seam instead.",
    },
    schema: [
      {
        additionalProperties: false,
        properties: { subject: { type: 'string' } },
        required: ['subject'],
        type: 'object',
      },
    ],
    type: 'problem',
  },
  name: 'fixture-role-imports',
});
