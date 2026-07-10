# 15. [Keeping contracts exports to zod schemas only](15-contracts-only-schemas.test.ts)

## 15.1 accepting schemas-only export surfaces

### 15.1.1 allows a module of zod imports and exported schema consts

### 15.1.2 allows type-only exports and type-only zod imports

### 15.1.3 allows non-exported schema consts and schema-building helpers feeding exported schemas

## 15.2 rejecting non-schema exports

### 15.2.1 flags an exported function

### 15.2.2 flags exported plain objects, function declarations, and classes

### 15.2.3 flags a non-schema value in an export specifier list while allowing schemas and type specifiers

## 15.3 opening imports while holding the export surface

### 15.3.1 allows imports from any module, value or type

### 15.3.2 allows building and re-exporting schemas from any source

### 15.3.3 flags re-exporting non-schema values while allowing type-only re-exports

### 15.3.4 flags value star re-exports as unverifiable while allowing type-only star re-exports

## 15.4 freeing local statements while covering every export form

### 15.4.1 allows non-schema locals, mutable bindings, and side-effecting statements

### 15.4.2 checks a default export against the schemas-only surface

### 15.4.3 flags a mutable exported binding

## 15.5 scoping the rule to contracts files in the shipped config

### 15.5.1 enables the rule only for src contracts files
