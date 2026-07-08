# 13. [Removing type annotations the compiler already infers](13-no-type-annotations-redundant.test.ts)

## 13.1 removing redundant arrow return types

### 13.1.1 removes an inferrable arrow return type, standalone or as an object property

### 13.1.2 removes a return type despite a default parameter value or an as const literal

### 13.1.3 removes the return type of a nested arrow inside an exported boundary

## 13.2 removing redundant parameter types

### 13.2.1 removes a callback parameter type fixed by its contextual type

### 13.2.2 removes a parameter type that restates the declared function type, keeping the variable annotation

### 13.2.3 removes both a redundant return type and a contextual parameter on the same callback

## 13.3 removing variable and class field types that restate their initializers

### 13.3.1 removes annotations restating identifier and member-access initializers

### 13.3.2 removes annotations restating binary, unary, and template-literal initializers

### 13.3.3 removes an annotation restating a named interface type from an identifier initializer

### 13.3.4 removes a class property annotation restating its initializer

## 13.4 keeping load-bearing parameter annotations

### 13.4.1 keeps a standalone parameter annotation, which has no contextual type

### 13.4.2 keeps annotations whose contextual type merely echoes them through generic inference

### 13.4.3 keeps a parameter that deliberately widens past the contextual type

## 13.5 keeping return annotations at module boundaries and special returns

### 13.5.1 keeps a type predicate return

### 13.5.2 keeps annotations on exported, default-exported, and re-exported arrows

### 13.5.3 keeps a recursive arrow return and a generic return that inference would widen

## 13.6 keeping load-bearing variable annotations

### 13.6.1 keeps annotations that widen their initializer

### 13.6.2 keeps annotations over new, call, object-literal, and empty-array initializers

### 13.6.3 keeps annotations on exported and re-exported variables

## 13.7 confining redundancy checks to arrows

### 13.7.1 leaves class members and ambient declarations alone

### 13.7.2 leaves function declarations, expressions, and generators alone

### 13.7.3 leaves getters, method shorthands, interface signatures, and constructors alone
