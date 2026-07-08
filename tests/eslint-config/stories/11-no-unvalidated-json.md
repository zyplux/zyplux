# 11. [Requiring schema validation at JSON read boundaries](11-no-unvalidated-json.test.ts)

## 11.1 flagging JSON reads that bypass schema validation

### 11.1.1 flags a bare JSON parse assigned to a variable, naming the api in the message

### 11.1.2 flags a JSON parse annotated unknown, read off, or passed to a non-zod consumer

### 11.1.3 flags an awaited json call returning an any promise, naming the api in the message

### 11.1.4 flags a non-awaited any promise json call, caught by type rather than syntax

### 11.1.5 flags a synchronous json call returning any

## 11.2 permitting validated reads and non-boundary json calls

### 11.2.1 allows a JSON parse flowing directly into schema parse or safe parse

### 11.2.2 allows an awaited json call flowing into schema parse or parse async

### 11.2.3 leaves JSON stringify alone, which is not a parse boundary

### 11.2.4 leaves json calls returning concrete types alone
