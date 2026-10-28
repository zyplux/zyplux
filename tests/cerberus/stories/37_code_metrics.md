# 37. [Reporting tracked repository metrics](test_37_code_metrics.py)

## 37.1 measuring source content

### 37.1.1 splits typescript into prose code and branches

### 37.1.2 measures each supported grammar without network access

Tests use a deterministic byte tokenizer while exercising real grammar parsers. Normal reports use the o200k_base tokenizer.

### 37.1.3 keeps prose unknown languages and binaries distinct

### 37.1.4 rolls up typescript without counting it twice

## 37.2 selecting files

### 37.2.1 reads tracked worktree content without changing the index

### 37.2.2 excludes lockfiles deleted files and custom report destinations

### 37.2.3 uses shared production ownership in scoped reports

## 37.3 reporting errors

### 37.3.1 reports empty scopes and missing repositories
