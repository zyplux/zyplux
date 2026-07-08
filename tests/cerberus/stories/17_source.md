# 17. [Reading a repo checkout](test_17_source.py)

## 17.1 identifying the repo behind a checkout

### 17.1.1 names the repo from the github repository environment variable

### 17.1.2 falls back to the checkout directory name when the env var is unset

## 17.2 reading and writing files in the checkout

### 17.2.1 reads the content of a file at a given path

### 17.2.2 returns nothing for a path that does not exist

### 17.2.3 writes content to a file at a given path

## 17.3 listing the tracked files in a checkout

### 17.3.1 lists tracked files and skips gitignored paths

### 17.3.2 falls back to walking the filesystem when git is unavailable

## 17.4 listing ci workflow files

### 17.4.1 lists yaml workflow files under github workflows by name

### 17.4.2 returns no workflows when there is no workflows directory

## 17.5 diffing paths changed against a ref

### 17.5.1 lists surface paths changed since the ref

### 17.5.2 excludes surface paths unchanged since the ref

### 17.5.3 counts uncommitted working-tree changes against the ref

## 17.6 surfacing unavailable git history

### 17.6.1 errors when git history cannot be read outside a repo

### 17.6.2 errors when the git binary is missing

## 17.7 caching reads through the run context

### 17.7.1 serves freshly written content to later reads in the same run

### 17.7.2 keys cached history reads by their arguments
