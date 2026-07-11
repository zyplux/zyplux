# 5. [Requiring named types for parameters instead of inline object literals](5-no-anonymous-param-type.test.ts)

## 5.1 flagging inline object types in parameter position

1. 5.1.1 flags a top-level inline object type on plain and destructured parameters
2. 5.1.2 flags function declaration and object method parameters
3. 5.1.3 reports each parameter with an inline object type
4. 5.1.4 flags an object literal as a union or intersection member
5. 5.1.5 reports every object literal in a union separately
6. 5.1.6 flags a parameter with a default value
7. 5.1.7 flags a constructor parameter property

## 5.2 permitting named, primitive, and non-parameter object types

1. 5.2.1 allows a named type reference, a primitive, and an untyped parameter
2. 5.2.2 allows inline object types outside parameter position
3. 5.2.3 allows an object literal that describes a container element, not the parameter
