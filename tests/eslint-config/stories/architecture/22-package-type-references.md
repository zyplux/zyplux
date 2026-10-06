# 22. [Checking package type references](22-package-type-references.test.ts)

## 22.1 using public package type exports

### 22.1.1 rejects a private type import

### 22.1.2 rejects an inline private type import

### 22.1.3 rejects a private type re-export

### 22.1.4 rejects an inline private type re-export

### 22.1.5 rejects a private import type expression

### 22.1.6 rejects a direct path to an exported source file

### 22.1.7 rejects a resolved private alias

### 22.1.8 public type-only imports and re-exports pass the export rule

### 22.1.9 imports within the provider can reach its internal files

### 22.1.10 a public value import does not authorize a private alias

### 22.1.11 value-only references are outside the type export rule

## 22.2 rejecting type-only implementation dependencies

### 22.2.1 rejects a type-only API import

### 22.2.2 rejects an inline type-only API import

### 22.2.3 rejects a type-only API re-export

### 22.2.4 rejects an inline type-only API re-export

### 22.2.5 rejects an API import type expression

### 22.2.6 public API types can accompany a value import in another consumer file

### 22.2.7 public contracts and interfaces need no implementation import

### 22.2.8 private entries belong to the package export rule

### 22.2.9 a private value import cannot establish a public API dependency

### 22.2.10 both rules report their own restriction without duplicate diagnostics
