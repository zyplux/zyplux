# 6. [Wrapping git and gh behind a typed shell harness](6-shell.test.ts)

## 6.1 translating flag objects into CLI arguments

### 6.1.1 omits a false boolean flag entirely

## 6.2 building git subcommands

### 6.2.1 builds git %s argv from its arguments and flags

## 6.3 building gh subcommands

### 6.3.1 builds gh %s argv from its arguments and flags

## 6.4 reading trimmed command output

### 6.4.1 awaits a command and trims its text output

## 6.5 invoking the shell function directly

### 6.5.1 forwards a direct call to the underlying shell harness

## 6.6 omitting optional flags falls back to defaults

### 6.6.1 omits any flags when %s is called without them

### 6.6.2 builds the same show toplevel argv when git.showToplevel is called without a cwd

## 6.7 reading typed GitHub run fields

### 6.7.1 returns selected fields as a typed object

### 6.7.2 validates and exposes only the selected fields

### 6.7.3 preserves an empty conclusion

### 6.7.4 rejects invalid JSON or missing or invalid selected fields: %s

### 6.7.5 propagates command failures before parsing stdout

### 6.7.6 infers selected fields and rejects invalid options at compile time

## 6.8 reading structured GitHub resources

### 6.8.1 validates and returns typed JSON for $name

### 6.8.2 rejects invalid fields for $name

### 6.8.3 propagates command failures for $name

### 6.8.4 accepts a review from a deleted author

## 6.9 checking an exact release tag

### 6.9.1 finds an existing release by its exact tag

### 6.9.2 returns false only when the release is absent

### 6.9.3 rejects an invalid lookup response: %s

### 6.9.4 propagates lookup failures instead of reporting a missing release
