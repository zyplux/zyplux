# 11. [Requiring schema validation at JSON read boundaries](11-no-unvalidated-json.test.ts)

## 11.1 flagging JSON reads that bypass schema validation

### 11.1.1 flags a bare JSON parse assigned to a variable, naming the api in the message

### 11.1.2 flags an awaited json call returning an any promise, naming the api in the message

1. flags a JSON parse annotated unknown
2. flags a JSON parse read off before validation
3. flags a JSON parse passed to a non-zod consumer
4. flags a non-awaited any promise json call, caught by type rather than syntax
5. flags a synchronous json call returning any

## 11.2 permitting validated reads and non-boundary json calls

1. allows a JSON parse flowing into schema parse
2. allows a JSON parse flowing into schema safe parse
3. allows an awaited json call flowing into schema parse
4. allows an awaited json call flowing into schema parse async
5. leaves JSON stringify alone, which is not a parse boundary
6. leaves a json call returning a concrete type alone
7. leaves a json call with a concrete return type built from an argument alone
