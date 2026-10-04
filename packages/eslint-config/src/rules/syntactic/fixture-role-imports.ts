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
        "Keep a flat test suite's subject package behind its arrange/act fixtures: only fixtures/arrange.ts and fixtures/act.ts may import the subject. Other modules under fixtures/ are reported, except imports of the subject's behavior-free `/contracts` seam. The shipped config discovers the subject by pairing tests/<basename> with its workspace package. Cerberus's fixture_roles_ts bite checks fixture entry points for flat and domain suites.",
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
