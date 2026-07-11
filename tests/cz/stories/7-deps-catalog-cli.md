# 7. [Writing the resolved dependency catalog to disk](7-deps-catalog-cli.test.ts)

## 7.1 writing the resolved repos to the output file

### 7.1.1 writes the sorted repos as indented json and reports the count

### 7.1.2 reports unresolved dependencies alongside the written count

## 7.2 resolving the output path

- joins a relative --out under --dir
- uses an absolute --out as-is
