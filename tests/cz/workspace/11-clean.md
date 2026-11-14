# 11. [Removing gitignored build artifacts and caches](11-clean.test.ts)

## 11.1 cleaning a single repo

### 11.1.1 removes gitignored build artifacts and caches

### 11.1.2 protects dotenv files by default even though they are gitignored

### 11.1.3 dry-run reports what would be removed without deleting anything

### 11.1.4 reports nothing to clean when no gitignored artifacts exist

## 11.2 discovering every repo under a non-repo directory

### 11.2.1 cleans every nested git repo found under the current directory

### 11.2.2 discovers repos in dot-prefixed directories too

## 11.3 excluding paths

### 11.3.1 skips a whole repo named by --exclude

### 11.3.2 protects a subfolder named by --exclude within a cleaned repo

### 11.3.3 does not let a skipped repo name protect a same-named ignored subfolder elsewhere

## 11.4 error handling

### 11.4.1 fails when no git repo is found at or under the current directory
