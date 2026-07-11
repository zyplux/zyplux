# 16. [Keeping schema construction inside contracts modules](16-no-schemas-outside-contracts.test.ts)

## 16.1 keeping schema construction in contracts

1. 16.1.1 flags a zod value import and the schema const it builds
2. 16.1.2 flags a schema composed inline from an imported contracts schema
3. 16.1.3 reports a construction chain once at its declaration
4. 16.1.4 flags a named value import that exposes a schema factory
5. 16.1.5 flags a named object import that exposes a schema factory

## 16.2 allowing schema use outside contracts

1. 16.2.1 allows importing a contracts schema and parsing with it
2. 16.2.2 allows a schema-typed parameter and type-only zod import
3. 16.2.3 allows a type-only import combined with a value import
4. 16.2.4 allows an inferred type from an imported contracts schema
5. 16.2.5 allows named zod values that cannot build schemas

## 16.3 scoping the rule to every typescript file in the shipped config

### 16.3.1 enables the rule for every typescript file while exempting the contracts modules
