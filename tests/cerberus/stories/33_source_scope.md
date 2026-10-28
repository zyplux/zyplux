# 33. [Classifying production and test source](test_33_source_scope.py)

## 33.1 sharing repository source classification

### 33.1.1 classifies application and infrastructure files with bundled defaults

The public API classifies repository-relative paths without requiring files on disk. Production roots contain application and package source; infra, demo, test and docs have their own categories. Test directories and conventional test filenames remain test code.

### 33.1.2 replaces production roots without replacing test defaults

### 33.1.3 overrides test file patterns without replacing production defaults

### 33.1.4 explains how to replace tool specific production settings

## 33.2 sharing testing eligibility

### 33.2.1 separates categories from colocated tests and testing eligibility

Demo ownership is declared for its actual source and test directories. A product test using demo fixtures retains its product ownership. Prod and infra source need tests; demo, test and docs source do not.

### 33.2.2 prefers deeper and more specific categories

### 33.2.3 rejects ambiguous categories

### 33.2.4 keeps testing exceptions in the shared declaration

### 33.2.5 rejects other categories inside demos

Demo scopes are terminal: everything beneath a declared demo directory is demo code. Linting and typechecking still apply.
