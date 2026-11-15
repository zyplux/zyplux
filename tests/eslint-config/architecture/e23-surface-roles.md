# e23. [Assigning public surface roles](e23-surface-roles.test.ts)

## e23.1 requiring pure barrels

### e23.1.1 accepts named and star re-exports

### e23.1.2 rejects a local declaration

### e23.1.3 rejects registration in the entry

## e23.2 enforcing type-only modules

### e23.2.1 accepts interfaces and aliases

### e23.2.2 accepts inline type imports

### e23.2.3 rejects runtime imports

### e23.2.4 rejects runtime constants

### e23.2.5 accepts type star re-exports

## e23.3 assigning constants their primitive role

### e23.3.1 accepts primitive constants

### e23.3.2 rejects object constants

### e23.3.3 rejects mutable constants

### e23.3.4 rejects functions

### e23.3.5 rejects type exports

### e23.3.6 accepts primitive unions

## e23.4 locating violations at the public export

### e23.4.1 contracts report a runtime star re-export at its source line

### e23.4.2 constants reject type-only re-exports at the export specifier

## e23.5 applying the shipped architecture scopes

### e23.5.1 rejects runtime declarations in type modules

### e23.5.2 rejects declarations in exported roots

### e23.5.3 rejects direct helper imports throughout test suites
