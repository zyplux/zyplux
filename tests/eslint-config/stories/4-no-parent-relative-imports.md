# 4. [Restricting parent-relative (../) imports](4-no-parent-relative-imports.test.ts)

## 4.1 flagging parent-relative import specifiers

1. flags a parent import at any depth
2. flags a type only import from a parent path
3. flags a re export from a parent path

## 4.2 permitting non-parent-relative import specifiers

1. allows a same directory relative import
2. allows alias and bare package imports
