# 12. [Banning zod custom, the unverified type assertion](12-no-zod-custom.test.ts)

## 12.1 flagging zod custom in every import shape

1. flags z custom with a generic and a check function
2. flags z custom called without arguments
3. flags an aliased import of zod, caught by type origin rather than the name z
4. flags a namespace import of zod
5. flags z custom chained with parse

## 12.2 permitting real zod combinators and non-zod custom

1. allows the real zod object combinator
2. allows the real zod string combinator
3. allows the real zod discriminated union combinator
4. leaves a custom call not originating from zod alone
5. leaves a bare custom call alone
