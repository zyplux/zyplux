# 6. [Banning typed identity functions that act as disguised casts](6-no-identity-cast.test.ts)

## 6.1 flagging typed identity functions that act as disguised casts

1. 6.1.1 flags an expression-bodied identity with a typed parameter
2. 6.1.2 flags an identity that also annotates the return position
3. 6.1.3 flags a block-bodied identity with a single return
4. 6.1.4 flags function declaration and object method identities

## 6.2 permitting genuine pass-throughs and transforming bodies

1. 6.2.1 allows a generic identity, plain or constrained — the sanctioned pass-through
2. 6.2.2 allows an untyped parameter, which asserts no type
3. 6.2.3 allows a body that transforms the argument or returns a property
4. 6.2.4 allows more than one parameter and a block body that does more than return
