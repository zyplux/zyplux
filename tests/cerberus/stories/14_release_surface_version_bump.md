# 14. [Requiring a published target's version to be bumped whenever its release surface changes](test_14_release_surface_version_bump.py)

## 14.1 selecting release checks

### 14.1.1 skips repos that publish nothing

## 14.2 delegating release validation to Airlock

### 14.2.1 runs the installed airlock in the repository

### 14.2.2 reports airlock findings without reinterpreting release policy

### 14.2.3 preserves findings from multiple targets

## 14.3 reporting command failures

### 14.3.1 errors when pnpm is missing

### 14.3.2 reports an unavailable airlock command

### 14.3.3 rejects a failed command even if its findings pass

### 14.3.4 reports a failed command without stderr

### 14.3.5 preserves command errors written to stdout

## 14.4 validating structured findings

### 14.4.1 rejects malformed structured findings
