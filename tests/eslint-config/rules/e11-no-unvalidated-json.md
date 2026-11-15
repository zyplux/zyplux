# e11. [Requiring schema validation at JSON read boundaries](e11-no-unvalidated-json.test.ts)

## e11.1 flagging JSON reads that bypass schema validation

### e11.1.1 flags a bare JSON parse assigned to a variable, naming the api in the message

### e11.1.2 flags an awaited json call returning an any promise, naming the api in the message

### e11.1.3 flags a JSON parse annotated unknown
### e11.1.4 flags a JSON parse read off before validation
### e11.1.5 flags a JSON parse passed to a non-zod consumer
### e11.1.6 flags a non-awaited any promise json call, caught by type rather than syntax
### e11.1.7 flags a synchronous json call returning any

### e11.1.8 flags JSON passed to an unrelated validator
### e11.1.9 flags JSON passed to an unrelated async validator
### e11.1.10 flags JSON passed to an unrelated parser

### e11.1.11 flags a JSON promise passed into validation
### e11.1.12 flags a JSON promise passed into parsing
### e11.1.13 flags a JSON promise passed into functional validation
### e11.1.14 flags JSON used as validation options
### e11.1.15 flags a functional validator without a schema

## e11.2 permitting validated reads and non-boundary json calls

1. allows a JSON parse flowing into schema parse
2. allows a JSON parse flowing into schema safe parse
3. allows an awaited json call flowing into schema parse
4. allows an awaited json call flowing into schema parse async
5. leaves JSON stringify alone, which is not a parse boundary
6. leaves a json call returning a concrete type alone
7. leaves a json call with a concrete return type built from an argument alone
8. allows JSON flowing into boolean validation
9. allows JSON flowing into asynchronous boolean validation
10. allows namespace boolean validation
11. allows imported boolean validation
12. allows functional parsing
13. allows namespace async validation of resolved JSON
14. allows imported async validation of resolved JSON
15. allows instance async validation of resolved JSON
