# 7. [Banning user-defined type predicates in favor of runtime validation](7-no-type-predicate.test.ts)

## 7.1 flagging user-defined type guards in every function form

1. 7.1.1 flags arrow, declaration, and expression type guards
2. 7.1.2 flags class method and interface method signature type guards
3. 7.1.3 flags function type alias and ambient declaration type guards
4. 7.1.4 flags a this-based type guard

## 7.2 permitting predicate-free checks and assertion signatures

1. 7.2.1 allows a boolean check without a predicate annotation
2. 7.2.2 allows assertion signatures, with or without a predicate
3. 7.2.3 allows a regular typed function with no predicate
