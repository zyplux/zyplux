# 16. [Keeping schema construction inside contracts modules](16-no-schemas-outside-contracts.test.ts)

## 16.1 keeping schema construction in contracts

1. flags a zod value import and the schema const it builds
2. flags a schema composed inline from an imported contracts schema
3. reports a construction chain once at its declaration
4. flags a named value import that exposes a schema factory
5. flags a named object import that exposes a schema factory

## 16.2 allowing schema use outside contracts

1. allows importing a contracts schema and parsing with it
2. allows a schema-typed parameter and type-only zod import
3. allows a type-only import combined with a value import
4. allows an inferred type from an imported contracts schema
5. allows named zod values that cannot build schemas

## 16.3 scoping the rule to every typescript file in the shipped config

### 16.3.1 enables the rule for every typescript file while exempting the contracts modules
