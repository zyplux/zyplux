# 8. [Destructuring parameters that are only read for their properties](8-prefer-destructured-params.test.ts)

## 8.1 rewriting property-only parameters into destructuring patterns

1. rewrites a single property read in a concise body
2. turns several distinct properties into several bindings and a repeated read into one
3. rewrites function declaration and object method parameters
4. absorbs a const alias whose name already matches the property
5. absorbs a const alias under a different name, renaming its references to the property
6. combines an alias and a direct read into one pattern
7. treats a non-const alias as a direct read, leaving the local binding in place
8. destructures only the property-only parameter, leaving a method-receiver parameter alone

## 8.2 reporting without an autofix when destructuring would collide

1. reports a collision with a function-scoped local without offering an autofix
2. reports a same-named local alias clash without offering an autofix
3. reports a collision with a nested-scope binding without offering an autofix

## 8.3 permitting parameters that need their whole object

1. leaves an untyped parameter alone
2. leaves two parameters that would destructure to the same name alone
3. leaves a whole object that is returned, passed on, or compared alone
4. leaves method calls, computed access, and optional access alone
5. leaves member writes, reserved-word properties, and already-destructured parameters alone
6. leaves an unused parameter and a free-variable capture alone
7. leaves a union-typed parameter whose property read depends on narrowing alone
