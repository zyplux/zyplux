# 18. [Preferring type aliases while keeping augmentation interfaces](18-type-over-interface.test.ts)

## 18.1 rewriting interfaces into type aliases

### 18.1.1 fixes a plain interface into an equivalent type alias, normalizing whitespace

### 18.1.2 fixes extends clauses into intersections and keeps type parameters

### 18.1.3 fixes a default-exported interface into a named type alias with a default export

### 18.1.4 leaves a type alias alone, never preferring interfaces

### 18.1.5 fixes an interface behind export and declare modifiers, keeping them in place

## 18.2 exempting declaration-merging interfaces

### 18.2.1 allows interfaces inside declare module and declare global blocks

### 18.2.2 flags and fixes an interface inside a plain namespace, which does not merge upstream

### 18.2.3 allows interfaces inside a declare namespace, whose ambient declarations merge

### 18.2.4 allows an interface nested in a namespace inside declare global

### 18.2.5 flags and fixes an interface inside a global block that lacks the declare keyword

## 18.3 replacing the upstream preference in the shipped config

### 18.3.1 enables the rule for every typescript file

### 18.3.2 resolves the upstream consistent-type-definitions rule to off
