# 15. [Keeping contracts exports to zod schemas only](15-contracts-only-schemas.test.ts)

## 15.1 accepting schemas-only export surfaces

1. 15.1.1 allows a module of zod imports and exported schema consts
2. 15.1.2 allows type-only exports and type-only zod imports
3. 15.1.3 allows non-exported schema consts and schema-building helpers feeding exported schemas

## 15.2 rejecting non-schema exports

1. 15.2.1 flags an exported function
2. 15.2.2 flags an exported plain object
3. 15.2.3 flags an exported function declaration
4. 15.2.4 flags an exported class
5. 15.2.5 flags a non-schema value in an export specifier list while allowing schemas and type specifiers

## 15.3 opening imports while holding the export surface

1. 15.3.1 allows a node builtin import
2. 15.3.2 allows a relative import
3. 15.3.3 allows a type-only import from an external module
4. 15.3.4 allows an import from an internal alias
5. 15.3.5 allows building and re-exporting a schema composed from an imported contracts schema
6. 15.3.6 allows building and re-exporting a schema derived via a transform
7. 15.3.7 allows re-exporting an imported contracts schema by name
8. 15.3.8 flags re-exporting a non-schema value from a relative module
9. 15.3.9 flags re-exporting a non-schema value from zod
10. 15.3.10 allows a type-only re-export
11. 15.3.11 flags a value star re-export from zod as unverifiable
12. 15.3.12 flags a value star re-export from a contracts module as unverifiable
13. 15.3.13 allows a type-only star re-export

## 15.4 freeing local statements while covering every export form

1. 15.4.1 allows non-schema locals, mutable bindings, and side-effecting statements
2. 15.4.2 checks a default export of a schema against the schemas-only surface
3. 15.4.3 flags a default export of a non-schema value
4. 15.4.4 flags a mutable exported binding

## 15.5 scoping the rule to contracts files in the shipped config

### 15.5.1 enables the rule only for src contracts files
