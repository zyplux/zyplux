# 3. [Reporting tracked repository metrics](test_3_code_metrics.py)

## 3.1 measuring source content

### 3.1.1 splits typescript into prose code and branches

### 3.1.2 measures each supported grammar without network access

Tests use a deterministic byte tokenizer while exercising real grammar parsers. Normal reports use the o200k_base tokenizer.

### 3.1.3 keeps prose unknown languages and binaries distinct

### 3.1.4 rolls up typescript without counting it twice

## 3.2 selecting files

### 3.2.1 reads tracked worktree content without changing the index

### 3.2.2 excludes lockfiles deleted files and custom report destinations

### 3.2.3 uses shared production ownership in scoped reports

## 3.3 reporting errors

### 3.3.1 reports empty scopes and missing repositories
