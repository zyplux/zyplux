# cz11. [Removing gitignored build artifacts and caches](cz11-clean.test.ts)

## cz11.1 cleaning a single repo

### cz11.1.1 removes gitignored build artifacts and caches

### cz11.1.2 protects dotenv files by default even though they are gitignored

### cz11.1.3 dry-run reports what would be removed without deleting anything

### cz11.1.4 reports nothing to clean when no gitignored artifacts exist

## cz11.2 discovering every repo under a non-repo directory

### cz11.2.1 cleans every nested git repo found under the current directory

### cz11.2.2 discovers repos in dot-prefixed directories too

## cz11.3 excluding paths

### cz11.3.1 skips a whole repo named by --exclude

### cz11.3.2 protects a subfolder named by --exclude within a cleaned repo

### cz11.3.3 does not let a skipped repo name protect a same-named ignored subfolder elsewhere

## cz11.4 error handling

### cz11.4.1 fails when no git repo is found at or under the current directory
