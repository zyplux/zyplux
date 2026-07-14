# 15. [Keeping contracts exports to zod schemas only](15-contracts-only-schemas.test.ts)

## 15.1 accepting schemas-only export surfaces

1. allows a module of zod imports and exported schema consts
2. allows type-only exports and type-only zod imports
3. allows non-exported schema consts and schema-building helpers feeding exported schemas

## 15.2 rejecting non-schema exports

1. flags an exported function
2. flags an exported plain object
3. flags an exported function declaration
4. flags an exported class
5. flags a non-schema value in an export specifier list while allowing schemas and type specifiers

## 15.3 opening imports while holding the export surface

1. allows a node builtin import
2. allows a relative import
3. allows a type-only import from an external module
4. allows an import from an internal alias
5. allows building and re-exporting a schema composed from an imported contracts schema
6. allows building and re-exporting a schema derived via a transform
7. allows re-exporting an imported contracts schema by name
8. flags re-exporting a non-schema value from a relative module
9. flags re-exporting a non-schema value from zod
10. allows a type-only re-export
11. flags a value star re-export from zod as unverifiable
12. flags a value star re-export from a contracts module as unverifiable
13. allows a type-only star re-export

## 15.4 freeing local statements while covering every export form

1. allows non-schema locals, mutable bindings, and side-effecting statements
2. checks a default export of a schema against the schemas-only surface
3. flags a default export of a non-schema value
4. flags a mutable exported binding

## 15.5 scoping the rule to contracts files in the shipped config

### 15.5.1 enables the rule only for src contracts files
