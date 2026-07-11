# 18. [Preferring type aliases while keeping augmentation interfaces](18-type-over-interface.test.ts)

## 18.1 rewriting interfaces into type aliases

1. 18.1.1 fixes a plain interface into an equivalent type alias
2. 18.1.2 normalizes squeezed whitespace before the brace
3. 18.1.3 normalizes stretched whitespace before the brace
4. 18.1.4 fixes an extends clause into an intersection
5. 18.1.5 keeps a type parameter on the fixed alias
6. 18.1.6 fixes multiple extends clauses into an intersection
7. 18.1.7 keeps type arguments on extended intersection members
8. 18.1.8 fixes a default-exported interface into a named type alias with a default export
9. 18.1.9 fixes an interface behind export and declare modifiers, keeping them in place
10. 18.1.10 leaves a plain type alias alone
11. 18.1.11 leaves a type alias with an intersection alone

## 18.2 exempting declaration-merging interfaces

1. 18.2.1 flags and fixes an interface inside a plain namespace, which does not merge upstream
2. 18.2.2 flags and fixes an interface inside a global block that lacks the declare keyword
3. 18.2.3 allows an interface inside a declare module block
4. 18.2.4 allows an interface inside a declare global block
5. 18.2.5 allows interfaces inside a declare namespace, whose ambient declarations merge
6. 18.2.6 allows an interface nested in a namespace inside declare global

## 18.3 replacing the upstream preference in the shipped config

### 18.3.1 enables the rule for every typescript file

### 18.3.2 resolves the upstream consistent-type-definitions rule to off
