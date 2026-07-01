# 4. [Restricting parent-relative (../) imports](4_no-parent-relative-imports.test.ts)

## 4.1 flagging parent-relative import specifiers

### 4.1.1 flags a single level parent import

### 4.1.2 flags a deep parent import spanning multiple levels

### 4.1.3 flags a type only import from a parent path

### 4.1.4 flags a re export from a parent path

## 4.2 permitting non-parent-relative import specifiers

### 4.2.1 allows a same directory relative import

### 4.2.2 allows a path alias import

### 4.2.3 allows a bare package import

## 4.3 scoping the restriction to import declarations

### 4.3.1 leaves a non import string argument untouched
