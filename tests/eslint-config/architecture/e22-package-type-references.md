# e22. [Checking package type references](e22-package-type-references.test.ts)

## e22.1 using public package type exports

### e22.1.1 rejects a private type import

### e22.1.2 rejects an inline private type import

### e22.1.3 rejects a private type re-export

### e22.1.4 rejects an inline private type re-export

### e22.1.5 rejects a private import type expression

### e22.1.6 rejects a direct path to an exported source file

### e22.1.7 rejects a resolved private alias

### e22.1.8 public type-only imports and re-exports pass the export rule

### e22.1.9 imports within the provider can reach its internal files

### e22.1.10 a public value import does not authorize a private alias

### e22.1.11 value-only references are outside the type export rule

## e22.2 rejecting type-only implementation dependencies

### e22.2.1 rejects a type-only API import

### e22.2.2 rejects an inline type-only API import

### e22.2.3 rejects a type-only API re-export

### e22.2.4 rejects an inline type-only API re-export

### e22.2.5 rejects an API import type expression

### e22.2.6 public API types can accompany a value import in another consumer file

### e22.2.7 public contracts and interfaces need no implementation import

### e22.2.8 private entries belong to the package export rule

### e22.2.9 a private value import cannot establish a public API dependency

### e22.2.10 both rules report their own restriction without duplicate diagnostics
