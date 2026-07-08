# 15. [Keeping contracts modules to zod schemas only](15-contracts-only-schemas.test.ts)

## 15.1 accepting purely declarative contracts modules

### 15.1.1 allows a module of zod imports and exported schema consts

### 15.1.2 allows type-only exports and type-only zod imports

### 15.1.3 allows non-exported schema consts and schema-building helpers feeding exported schemas

## 15.2 rejecting non-schema exports

### 15.2.1 flags an exported function

### 15.2.2 flags exported plain objects, function declarations, and classes

### 15.2.3 flags a non-schema value in an export specifier list while allowing schemas and type specifiers

## 15.3 rejecting non-zod module edges

### 15.3.1 flags imports from anything but zod, whether value, type, alias, or builtin

### 15.3.2 flags re-exports from other modules

## 15.4 rejecting non-declarative statements

### 15.4.1 flags non-schema local declarations and non-const bindings

### 15.4.2 flags side-effecting statements and default exports

## 15.5 scoping the rule to contracts files in the shipped config

### 15.5.1 enables the rule only for src contracts files
