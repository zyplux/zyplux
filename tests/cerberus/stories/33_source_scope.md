# 33. [Classifying production and test source](test_33_source_scope.py)

## 33.1 sharing repository source ownership

### 33.1.1 classifies application and infrastructure files with bundled defaults

The public API classifies repository-relative paths without requiring files on disk. Application, package, and infrastructure roots own their source and configuration; test directories and conventional test filenames remain test code. Development tooling outside those roots is not production.

### 33.1.2 replaces production roots without replacing test defaults

### 33.1.3 overrides test file patterns without replacing production defaults

### 33.1.4 explains how to replace tool specific production settings
