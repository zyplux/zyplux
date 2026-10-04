# 21. [Limiting nested calls while allowing Zod schemas](21-max-nested-calls.test.ts)

## 21.1 preserving the call depth limit

### 21.1.1 rejects excessive nesting for %s

### 21.1.2 accepts calls at the default limit

### 21.1.3 honors the configured limit

### 21.1.4 resets depth at a %s

### 21.1.5 does not count fluent receiver calls as nested arguments

## 21.2 exempting schema construction precisely

### 21.2.1 accepts deeply nested object and array schemas

### 21.2.2 recognizes aliased imports and factories returning schemas

### 21.2.3 recognizes unions consisting entirely of schemas

### 21.2.4 still checks ordinary calls inside schema arguments

### 21.2.5 still checks computation inside schema callbacks

### 21.2.6 replaces Unicorn only for TypeScript files

## 21.3 sharing schema collection detection

### 21.3.1 exempts nested calls returning plain schema collections

### 21.3.2 keeps the nesting limit for mixed objects
