# 14. [Flagging annotations that narrow away members the value actually has](14-no-type-annotations-narrowing.test.ts)

## 14.1 flagging variable annotations that hide members of their initializer

1. 14.1.1 flags a variable type hiding one member, suggesting removal
2. 14.1.2 flags a variable type hiding several members, suggesting removal
3. 14.1.3 flags hiding a member declared on a named interface in source position
4. 14.1.4 flags hiding a member declared on a named interface in annotation position
5. 14.1.5 flags a call-expression initializer
6. 14.1.6 flags a member-access initializer
7. 14.1.7 flags a never-reassigned let, which is effectively const
8. 14.1.8 flags upcasting a class instance to a subset of its members
9. 14.1.9 flags a readonly fiction over a fresh mutable Set
10. 14.1.10 flags a readonly fiction over a mutable array
11. 14.1.11 flags a bare function-type annotation hiding a property of the callable value

## 14.2 flagging return annotations that hide members of the returned value

1. 14.2.1 flags a concise arrow return type
2. 14.2.2 flags a block-bodied arrow return type
3. 14.2.3 flags a function declaration return type
4. 14.2.4 flags a method return type
5. 14.2.5 flags a member common to every return that the return type hides
6. 14.2.6 does not mistake the returns of a nested function for the outer return
7. 14.2.7 flags a nested arrow inside an exported boundary, which is still internal
8. 14.2.8 flags a function-type return annotation hiding a property of the returned callable value

## 14.3 flagging module boundaries all the same

1. 14.3.1 flags an exported arrow return type
2. 14.3.2 flags an exported variable annotation
3. 14.3.3 flags a re-exported variable annotation
4. 14.3.4 flags an exported function declaration return type
5. 14.3.5 flags a method return type of an exported class

## 14.4 flagging class field annotations that hide members of their initializer

1. 14.4.1 flags a mutable class field
2. 14.4.2 flags a readonly class field
3. 14.4.3 flags a field of an exported class
4. 14.4.4 flags a class field typed as ReadonlySet over a fresh mutable Set

## 14.5 permitting annotations that hide nothing

1. 14.5.1 allows an annotation matching the value exactly for a variable
2. 14.5.2 allows an annotation matching the value exactly for a class field
3. 14.5.3 allows widening a literal type
4. 14.5.4 allows widening a literal initializer type
5. 14.5.5 allows widening array element types
6. 14.5.6 allows widening a class field literal type
7. 14.5.7 allows erasing to unknown
8. 14.5.8 allows an open index-signature dictionary
9. 14.5.9 allows a member missing from some return branch, which is not common to all returns
10. 14.5.10 leaves async return types alone, whose body type is the resolved value

## 14.6 permitting annotations the workaround cannot replace

1. 14.6.1 allows a reassigned let
2. 14.6.2 allows a class field reassigned to a narrower value
3. 14.6.3 allows a recursive arrow return
4. 14.6.4 allows a generic return referencing a type parameter
5. 14.6.5 allows an object literal that matches its annotation
6. 14.6.6 allows a function-type annotation over a plain function value that hides nothing
7. 14.6.7 allows a function-type annotation over an identical function type
