# 23. [Assigning public surface roles](23-surface-roles.test.ts)

## 23.1 requiring pure barrels

### 23.1.1 accepts named and star re-exports

### 23.1.2 rejects a local declaration

### 23.1.3 rejects registration in the entry

## 23.2 enforcing type-only modules

### 23.2.1 accepts interfaces and aliases

### 23.2.2 accepts inline type imports

### 23.2.3 rejects runtime imports

### 23.2.4 rejects runtime constants

### 23.2.5 accepts type star re-exports

## 23.3 assigning constants their primitive role

### 23.3.1 accepts primitive constants

### 23.3.2 rejects object constants

### 23.3.3 rejects mutable constants

### 23.3.4 rejects functions

### 23.3.5 rejects type exports

### 23.3.6 accepts primitive unions

## 23.4 locating violations at the public export

### 23.4.1 contracts report a runtime star re-export at its source line

### 23.4.2 constants reject type-only re-exports at the export specifier
