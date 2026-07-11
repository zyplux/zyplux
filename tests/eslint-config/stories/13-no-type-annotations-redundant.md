# 13. [Removing type annotations the compiler already infers](13-no-type-annotations-redundant.test.ts)

## 13.1 removing redundant arrow return types

1. 13.1.1 removes an inferrable arrow return type, standalone
2. 13.1.2 removes an inferrable arrow return type on an object property
3. 13.1.3 removes a return type despite a default parameter value
4. 13.1.4 removes a return type despite an as const literal
5. 13.1.5 removes the return type of a nested arrow inside an exported boundary

## 13.2 removing redundant parameter types

1. 13.2.1 removes a callback parameter type fixed by its contextual type
2. 13.2.2 removes a parameter type that restates the declared function type, keeping the variable annotation
3. 13.2.3 removes both a redundant return type and a contextual parameter on the same callback

## 13.3 removing variable and class field types that restate their initializers

1. 13.3.1 removes an annotation restating an identifier initializer
2. 13.3.2 removes an annotation restating a member-access initializer
3. 13.3.3 removes an annotation restating a binary initializer
4. 13.3.4 removes an annotation restating a unary initializer
5. 13.3.5 removes an annotation restating a template-literal initializer
6. 13.3.6 removes an annotation restating a named interface type from an identifier initializer
7. 13.3.7 removes a class property annotation restating its initializer

## 13.4 keeping load-bearing parameter annotations

1. 13.4.1 keeps a standalone parameter annotation, which has no contextual type
2. 13.4.2 keeps a parameter annotation echoed through generic inference in an object literal
3. 13.4.3 keeps a parameter annotation echoed through a generic higher order function
4. 13.4.4 keeps a parameter that deliberately widens past the contextual type

## 13.5 keeping return annotations at module boundaries and special returns

1. 13.5.1 keeps a type predicate return
2. 13.5.2 keeps a return type annotation on an exported arrow
3. 13.5.3 keeps a return type annotation on a default-exported arrow
4. 13.5.4 keeps a return type annotation on a re-exported arrow
5. 13.5.5 keeps a parameter type annotation on an exported variable-typed handler
6. 13.5.6 keeps a recursive arrow return type
7. 13.5.7 keeps a generic return type that inference would widen

## 13.6 keeping load-bearing variable annotations

1. 13.6.1 keeps an annotation that widens a literal initializer
2. 13.6.2 keeps an annotation that widens an undefined initializer
3. 13.6.3 keeps an annotation over a new expression initializer
4. 13.6.4 keeps an annotation over a call expression initializer
5. 13.6.5 keeps an annotation over an object-literal initializer
6. 13.6.6 keeps an annotation over an empty-array initializer
7. 13.6.7 keeps an annotation on an exported variable
8. 13.6.8 keeps an annotation on a re-exported variable

## 13.7 confining redundancy checks to arrows

1. 13.7.1 leaves a class member method alone
2. 13.7.2 leaves an ambient function declaration alone
3. 13.7.3 leaves an ambient class method alone
4. 13.7.4 leaves an async function declaration alone
5. 13.7.5 leaves a function expression alone
6. 13.7.6 leaves a function declaration alone
7. 13.7.7 leaves a generator function alone
8. 13.7.8 leaves a getter alone
9. 13.7.9 leaves a method shorthand alone
10. 13.7.10 leaves an interface method signature alone
11. 13.7.11 leaves a constructor parameter property alone
