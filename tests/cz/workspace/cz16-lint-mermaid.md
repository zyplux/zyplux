# cz16. [Linting Mermaid diagrams](cz16-lint-mermaid.test.ts)

## cz16.1 checking Markdown diagrams

### cz16.1.1 checks diagrams in nested Markdown files and ignores dependency and log folders

### cz16.1.2 reports each invalid diagram with its file and opening line

### cz16.1.3 succeeds with no diagrams and can run again after a parse failure

### cz16.1.4 checks tilde and longer backtick fences inside Markdown containers

### cz16.1.5 reports invalid diagrams across fence delimiters with their original lines

### cz16.1.6 keeps shorter and mismatched delimiters inside the diagram

### cz16.1.7 ignores fence examples inside other code blocks

### cz16.1.8 checks hidden files and directories while excluding dependency and log trees

### cz16.1.9 skips deleted tracked Markdown files
