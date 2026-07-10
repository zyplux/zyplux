# 16. [Keeping schema construction inside contracts modules](16-no-schemas-outside-contracts.test.ts)

## 16.1 keeping schema construction in contracts

### 16.1.1 flags a zod value import and the schema const it builds

### 16.1.2 flags a schema composed inline from an imported contracts schema

### 16.1.3 reports a construction chain once at its declaration

## 16.2 allowing schema use outside contracts

### 16.2.1 allows importing a contracts schema and parsing with it

### 16.2.2 allows type-only zod imports, schema-typed parameters, and inferred types

## 16.3 scoping the rule to source files in the shipped config

### 16.3.1 enables the rule for source files while exempting the contracts module
