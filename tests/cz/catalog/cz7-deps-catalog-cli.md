# cz7. [Writing the resolved dependency catalog to disk](cz7-deps-catalog-cli.test.ts)

## cz7.1 writing the resolved repos to the output file

### cz7.1.1 writes the sorted repos as indented json and reports the count

### cz7.1.2 reports unresolved dependencies alongside the written count

## cz7.2 resolving the output path

1. joins a relative --out under --dir
2. uses an absolute --out as-is
