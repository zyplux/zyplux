# e7. [Banning user-defined type predicates in favor of runtime validation](e7-no-type-predicate.test.ts)

## e7.1 flagging user-defined type guards in every function form

1. flags arrow, declaration, and expression type guards
2. flags class method and interface method signature type guards
3. flags function type alias and ambient declaration type guards
4. flags a this-based type guard

## e7.2 permitting predicate-free checks and assertion signatures

1. allows a boolean check without a predicate annotation
2. allows assertion signatures, with or without a predicate
3. allows a regular typed function with no predicate
