# 16. [Linting Mermaid diagrams](16-lint-mermaid.test.ts)

## 16.1 checking Markdown diagrams

### 16.1.1 checks diagrams in nested Markdown files and ignores dependency and log folders

### 16.1.2 reports each invalid diagram with its file and opening line

### 16.1.3 succeeds with no diagrams and can run again after a parse failure

### 16.1.4 checks tilde and longer backtick fences inside Markdown containers

### 16.1.5 reports invalid diagrams across fence delimiters with their original lines

### 16.1.6 keeps shorter and mismatched delimiters inside the diagram

### 16.1.7 ignores fence examples inside other code blocks
