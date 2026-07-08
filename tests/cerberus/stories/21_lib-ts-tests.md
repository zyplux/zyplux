# 21. [Enforcing the library test seam](test_21_lib-ts-tests.py)

## 21.1 scoping the check to libraries

### 21.1.1 skips repos with no typescript packages

### 21.1.2 skips workspaces with no library

### 21.1.3 leaves a published package without typescript sources unchecked

### 21.1.4 leaves a private test package unchecked

### 21.1.5 leaves a cli app to the cli seam check

### 21.1.6 covers a private package outside tests as a library

## 21.2 requiring library exports to expose only the root seam

### 21.2.1 passes a library that exports only the root seam

### 21.2.2 fails a library that declares no exports

### 21.2.3 fails and names each export beyond the root seam

### 21.2.4 fails a library whose exports omit the root entry

### 21.2.5 accepts a conditions object as the root seam

### 21.2.6 covers a published library under the tests directory

### 21.2.7 accepts a string exports as the root seam

### 21.2.8 accepts a contracts seam conditions object mapping to the contracts module

### 21.2.9 fails a contracts seam mapping elsewhere

### 21.2.10 fails an extra subpath beside a valid contracts seam

## 21.3 requiring story tests to reach workspace code only through fixture aliases

### 21.3.1 passes story tests importing only fixture aliases and node builtins

### 21.3.2 fails a story test importing the library directly

### 21.3.3 fails a story test reaching into library internals via a relative path

### 21.3.4 allows a story test to import a third party module directly

### 21.3.5 fails a story test importing a sibling workspace package

### 21.3.6 fails a story test pulling in library internals via a side effect import

## 21.4 keeping test package import aliases inside the package

### 21.4.1 fails an imports alias that escapes the test package
