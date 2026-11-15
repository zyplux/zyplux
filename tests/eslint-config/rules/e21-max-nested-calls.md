# e21. [Limiting nested calls while allowing Zod schemas](e21-max-nested-calls.test.ts)

## e21.1 preserving the call depth limit

### e21.1.1 rejects excessive nesting for %s

### e21.1.2 accepts calls at the default limit

### e21.1.3 honors the configured limit

### e21.1.4 resets depth at a %s

### e21.1.5 does not count fluent receiver calls as nested arguments

## e21.2 exempting schema construction precisely

### e21.2.1 accepts deeply nested object and array schemas

### e21.2.2 recognizes aliased imports and factories returning schemas

### e21.2.3 recognizes unions consisting entirely of schemas

### e21.2.4 still checks ordinary calls inside schema arguments

### e21.2.5 still checks computation inside schema callbacks

### e21.2.6 replaces Unicorn only for TypeScript files

## e21.3 sharing schema collection detection

### e21.3.1 exempts nested calls returning plain schema collections

### e21.3.2 keeps the nesting limit for mixed objects
