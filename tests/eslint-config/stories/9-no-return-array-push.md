# 9. [Banning use of the length returned by array push and unshift](9-no-return-array-push.test.ts)

## 9.1 flagging consumed push and unshift return values

1. flags the push or unshift length assigned to a variable
2. flags a push result passed as an argument or consumed by the void operator
3. flags awaiting an array push, unlike a promise-returning git push
4. flags a push result used as a logical operand
5. flags a push returned from an arrow with a concise body, offering no suggestion
6. flags a union-element array receiver and a cast wrapping the call

### 9.1.7 offers a split-into-statement suggestion when the push length is returned

## 9.2 permitting discarded pushes and non-array receivers

1. allows push and unshift as their own statements
2. allows an optional-chained push statement and a cast around a bare push
3. allows non-array receivers such as a promise-returning git push or a boolean stream push
4. allows an argument-less push, which is a length read rather than an append
5. leaves computed member access, free-standing push functions, and any receivers alone
