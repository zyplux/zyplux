# 14. [Flagging annotations that narrow away members the value actually has](14-no-type-annotations-narrowing.test.ts)

## 14.1 flagging variable annotations that hide members of their initializer

### 14.1.1 flags a variable type hiding one or several members, suggesting removal

### 14.1.2 flags hiding a member declared on a named interface, in source or annotation position

### 14.1.3 flags call-expression and member-access initializers

### 14.1.4 flags a never-reassigned let, which is effectively const

### 14.1.5 flags upcasting a class instance to a subset of its members

### 14.1.6 flags readonly fictions over fresh mutable collections

### 14.1.7 flags a bare function-type annotation hiding a property of the callable value

## 14.2 flagging return annotations that hide members of the returned value

### 14.2.1 flags concise and block-bodied arrow return types

### 14.2.2 flags function declaration and method return types

### 14.2.3 flags a member common to every return that the return type hides

### 14.2.4 does not mistake the returns of a nested function for the outer return

### 14.2.5 flags a nested arrow inside an exported boundary, which is still internal

### 14.2.6 flags a function-type return annotation hiding a property of the returned callable value

## 14.3 flagging module boundaries all the same

### 14.3.1 flags exported arrows, variables, and re-exported variables

### 14.3.2 flags exported function declarations and methods of exported classes

## 14.4 flagging class field annotations that hide members of their initializer

### 14.4.1 flags mutable, readonly, and exported-class fields alike

### 14.4.2 flags a class field typed as ReadonlySet over a fresh mutable Set

## 14.5 permitting annotations that hide nothing

### 14.5.1 allows an annotation matching the value exactly, for variables and class fields

### 14.5.2 allows widening literals and array element types

### 14.5.3 allows erasing to unknown and open index-signature dictionaries

### 14.5.4 allows a member missing from some return branch, which is not common to all returns

### 14.5.5 leaves async return types alone, whose body type is the resolved value

## 14.6 permitting annotations the workaround cannot replace

### 14.6.1 allows a reassigned let and a class field reassigned to a narrower value

### 14.6.2 allows recursive arrows and generic returns referencing a type parameter

### 14.6.3 allows an object literal that matches its annotation

### 14.6.4 allows function-type annotations over plain function values that hide nothing
