import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-return-array-push' });

const pushReport = [{ messageId: 'noReturnArrayPush' }];

describe('9.1 flagging consumed push and unshift return values', () => {
  test('9.1.1 flags the push or unshift length assigned to a variable', ({ lintRule }) => {
    expect(lintRule('declare const items: number[]; const length = items.push(1);')).toMatchObject(pushReport);
    expect(lintRule('declare const items: number[]; const length = items.unshift(1);')).toMatchObject(pushReport);
  });

  test('9.1.2 flags a push result passed as an argument or consumed by the void operator', ({ lintRule }) => {
    expect(lintRule('declare const items: number[]; console.log(items.push(1));')).toMatchObject(pushReport);
    expect(lintRule('declare const items: number[]; void items.push(1);')).toMatchObject(pushReport);
  });

  test('9.1.3 flags awaiting an array push, unlike a promise-returning git push', ({ lintRule }) => {
    expect(lintRule('declare const items: number[]; async function run() { await items.push(1); }')).toMatchObject(
      pushReport,
    );
  });

  test('9.1.4 flags a push result used as a logical operand', ({ lintRule }) => {
    expect(
      lintRule('declare const items: number[]; declare const ready: boolean; ready && items.push(1);'),
    ).toMatchObject(pushReport);
  });

  test('9.1.5 flags a push returned from an arrow with a concise body, offering no suggestion', ({ lintRule }) => {
    const messages = lintRule('declare const items: number[]; const add = (value: number) => items.push(value);');
    expect(messages).toMatchObject(pushReport);
    expect(messages[0]?.suggestions ?? []).toHaveLength(0);
  });

  test('9.1.6 flags a union-element array receiver and a cast wrapping the call', ({ lintRule }) => {
    expect(lintRule('declare const items: (number | string)[]; const length = items.push("a");')).toMatchObject(
      pushReport,
    );
    expect(lintRule('declare const items: number[]; const length = items.push(1) as number;')).toMatchObject(
      pushReport,
    );
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

describe('9.2 permitting discarded pushes and non-array receivers', () => {
  test('9.2.1 allows push and unshift as their own statements', ({ lintRule }) => {
    expect(lintRule('declare const items: number[]; items.push(1);')).toHaveLength(0);
    expect(lintRule('declare const items: number[]; items.unshift(1);')).toHaveLength(0);
  });

  test('9.2.2 allows an optional-chained push statement and a cast around a bare push', ({ lintRule }) => {
    expect(lintRule('declare const items: number[] | undefined; items?.push(1);')).toHaveLength(0);
    expect(lintRule('declare const items: number[]; items.push(1) as unknown;')).toHaveLength(0);
  });

  test('9.2.3 allows non-array receivers such as a promise-returning git push or a boolean stream push', ({
    lintRule,
  }) => {
    expect(
      lintRule(
        'declare const git: { push(remote: string, branch: string): Promise<void> }; async function run() { await git.push("origin", "main"); }',
      ),
    ).toHaveLength(0);
    expect(
      lintRule('declare const stream: { push(chunk: unknown): boolean }; const accepted = stream.push(1);'),
    ).toHaveLength(0);
  });

  test('9.2.4 allows an argument-less push, which is a length read rather than an append', ({ lintRule }) => {
    expect(lintRule('declare const items: number[]; const length = items.push();')).toHaveLength(0);
  });

  test('9.2.5 leaves computed member access, free-standing push functions, and any receivers alone', ({ lintRule }) => {
    expect(lintRule('declare const items: number[]; const length = items["push"](1);')).toHaveLength(0);
    expect(lintRule('declare function push(value: number): number; const length = push(1);')).toHaveLength(0);
    expect(lintRule('declare const bag: any; const length = bag.push(1);')).toHaveLength(0);
  });
});
