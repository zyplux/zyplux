import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-return-array-push' });

type PushCase = [shape: string, codes: string[], expectNoSuggestions?: true];

describe('9.1 flagging consumed push and unshift return values', () => {
  const cases: PushCase[] = [
    [
      '9.1.1 flags the push or unshift length assigned to a variable',
      [
        'declare const items: number[]; const length = items.push(1);',
        'declare const items: number[]; const length = items.unshift(1);',
      ],
    ],
    [
      '9.1.2 flags a push result passed as an argument or consumed by the void operator',
      [
        'declare const items: number[]; console.log(items.push(1));',
        'declare const items: number[]; void items.push(1);',
      ],
    ],
    [
      '9.1.3 flags awaiting an array push, unlike a promise-returning git push',
      ['declare const items: number[]; async function run() { await items.push(1); }'],
    ],
    [
      '9.1.4 flags a push result used as a logical operand',
      ['declare const items: number[]; declare const ready: boolean; ready && items.push(1);'],
    ],
    [
      '9.1.5 flags a push returned from an arrow with a concise body, offering no suggestion',
      ['declare const items: number[]; const add = (value: number) => items.push(value);'],
      true,
    ],
    [
      '9.1.6 flags a union-element array receiver and a cast wrapping the call',
      [
        'declare const items: (number | string)[]; const length = items.push("a");',
        'declare const items: number[]; const length = items.push(1) as number;',
      ],
    ],
  ];

  test.for(cases)('%s', ([, codes, expectNoSuggestions], { lintRule }) => {
    for (const code of codes) {
      const messages = lintRule(code);
      expect(messages).toReport('noReturnArrayPush');
      if (expectNoSuggestions === true) expect(messages[0]?.suggestions ?? []).toHaveLength(0);
    }
  });

  test('9.1.7 offers a split-into-statement suggestion when the push length is returned', ({
    applySuggestion,
    lintRule,
  }) => {
    const code = 'function run() { const items: number[] = []; return items.push(1); }';
    const messages = lintRule(code);
    expect(messages).toMatchObject([
      { messageId: 'noReturnArrayPush', suggestions: [{ messageId: 'separateReturn' }] },
    ]);
    const [message] = messages;
    if (message === undefined) throw new Error('expected a report');
    expect(applySuggestion(code, message)).toBe(
      'function run() { const items: number[] = []; items.push(1); return; }',
    );
  });
});

type ReportNothingCase = [shape: string, codes: string[]];

describe('9.2 permitting discarded pushes and non-array receivers', () => {
  const cases: ReportNothingCase[] = [
    [
      '9.2.1 allows push and unshift as their own statements',
      ['declare const items: number[]; items.push(1);', 'declare const items: number[]; items.unshift(1);'],
    ],
    [
      '9.2.2 allows an optional-chained push statement and a cast around a bare push',
      [
        'declare const items: number[] | undefined; items?.push(1);',
        'declare const items: number[]; items.push(1) as unknown;',
      ],
    ],
    [
      '9.2.3 allows non-array receivers such as a promise-returning git push or a boolean stream push',
      [
        'declare const git: { push(remote: string, branch: string): Promise<void> }; async function run() { await git.push("origin", "main"); }',
        'declare const stream: { push(chunk: unknown): boolean }; const accepted = stream.push(1);',
      ],
    ],
    [
      '9.2.4 allows an argument-less push, which is a length read rather than an append',
      ['declare const items: number[]; const length = items.push();'],
    ],
    [
      '9.2.5 leaves computed member access, free-standing push functions, and any receivers alone',
      [
        'declare const items: number[]; const length = items["push"](1);',
        'declare function push(value: number): number; const length = push(1);',
        'declare const bag: any; const length = bag.push(1);',
      ],
    ],
  ];

  test.for(cases)('%s', ([, codes], { expectEachToReportNothing, lintRule }) => {
    expectEachToReportNothing(lintRule, codes);
  });
});
