# 12. [Banning zod custom, the unverified type assertion](12-no-zod-custom.test.ts)

## 12.1 flagging zod custom in every import shape

### 12.1.1 flags z custom with a generic and check, and without arguments

### 12.1.2 flags aliased and namespace imports of zod, caught by type origin rather than the name z

### 12.1.3 flags z custom chained with parse

## 12.2 permitting real zod combinators and non-zod custom

### 12.2.1 allows real zod combinators such as object, string, and discriminated union

### 12.2.2 leaves custom calls that do not originate from zod alone
