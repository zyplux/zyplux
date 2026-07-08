# 20. [Enforcing the cli test seam](test_20_cli-ts-tests.py)

## 20.1 scoping the check to cli apps

### 20.1.1 skips repos with no typescript packages

### 20.1.2 skips workspaces with no cli app

## 20.2 requiring cli app exports to expose only the root seam

### 20.2.1 passes a cli app that exports only the root seam

### 20.2.2 fails a cli app that declares no exports

### 20.2.3 fails and names each export beyond the root seam

### 20.2.4 fails a cli app whose exports omit the root entry

### 20.2.5 accepts a conditions object as the root seam

### 20.2.6 accepts a contracts seam mapping to the contracts module

### 20.2.7 fails a contracts seam mapping elsewhere

## 20.3 requiring story tests to import only fixture aliases and node builtins

### 20.3.1 passes story tests importing only fixture aliases and node builtins

### 20.3.2 fails a story test importing the app package directly

### 20.3.3 fails a story test reaching into app internals via a relative path

## 20.4 keeping test package import aliases inside the package

### 20.4.1 fails an imports alias that escapes the test package
