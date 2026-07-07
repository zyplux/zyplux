# 15. [Requiring Python and TypeScript packages to back their public interface with story tests](test_15_story-tests.py)

## 15.1 scoping the check to real workspace packages

### 15.1.1 skips a repo with no python packages at all

### 15.1.2 skips a repo with no typescript packages at all

### 15.1.3 ignores a directory outside the workspace glob

### 15.1.4 excludes the top level tests directory from being treated as a package

### 15.1.5 treats a nested tests directory as excluded but still checks its sibling package

### 15.1.6 recognizes a workspaces object with a packages list

## 15.2 requiring a package that exposes a public interface to carry story tests

### 15.2.1 fails a python package that exposes a cli script but has no story tests

### 15.2.2 fails a typescript package that exposes a bin entry but has no story tests

### 15.2.3 skips a python package with no public interface and no tests

### 15.2.4 skips a typescript package with no public interface and no tests

### 15.2.5 fails a python package that already has plain tests but no story docs

### 15.2.6 fails a typescript package that already has plain tests but no story docs

## 15.3 resolving where a package stories directory lives

### 15.3.1 passes a python workspace member with colocated story tests

### 15.3.2 passes a typescript workspace member with colocated story tests

### 15.3.3 passes a workspace member whose story tests are torn out to a top level tests directory

## 15.4 matching story doc criteria against their tests

### 15.4.1 flags a story header with no matching test

### 15.4.2 flags a test with no matching story header

### 15.4.3 flags a title that has drifted between the header and its test

### 15.4.4 flags a criterion filed under the wrong section doc

### 15.4.5 does not flag titles that differ only by punctuation or case

## 15.5 keeping a story doc title linked to its test file

### 15.5.1 flags a stale header link

### 15.5.2 rewrites a stale header link and passes on the next run

### 15.5.3 flags a linked criterion header for unlinking

## 15.6 recognizing typescript test call syntax

### 15.6.1 recognizes test calls written with chained modifiers

### 15.6.2 recognizes test calls written with a parametrized each table

### 15.6.3 recognizes a title that contains a different quote character than its delimiter

## 15.7 running the python and typescript checks independently

### 15.7.1 scopes each check to only its own language packages in a mixed repo
