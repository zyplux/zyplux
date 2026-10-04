# 16. [Keeping schema exports in contracts modules](16-no-schemas-outside-contracts.test.ts)

## 16.1 keeping schema exports in contracts

1. flags an exported schema declaration
2. flags a schema exported after its declaration
3. flags a default schema export

## 16.2 allowing local schema implementation

1. allows zod imports and local schema construction
2. allows composing an imported schema locally
3. allows a schema-typed parameter and type-only zod import
4. allows an inferred type from an imported contracts schema
5. allows non-schema declaration exports

## 16.3 scoping the rule to implementation files

### 16.3.1 enables the rule while exempting contracts entrypoints and child modules

## 16.4 keeping schema collections in contracts

### 16.4.1 rejects schema collection exports: %s

### 16.4.2 permits ordinary configuration objects
