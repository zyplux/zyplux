# 40. [Deriving testing policy from source ownership](test_40_testing_scope.py)

## 40.1 selecting measured source

### 40.1.1 derives coverage from all eligible kinds

Product, infrastructure, and tooling modules enter coverage. Demo source and tests, including support packages and doubles, stay outside the denominator.

### 40.1.2 excludes explicit testing exemptions and empty source sets

### 40.1.3 excludes examples nested inside workspace packages

## 40.2 integrating with pytest and coverage

### 40.2.1 skips demo suites and counts unexecuted modules and subprocesses

The real runners exercise a product test using demo fixtures, ignore the demo-owned suite, include an unexecuted namespace module, and retain subprocess coverage after changing directories. The unchanged 90% floor fails when maintained modules remain untested.

### 40.2.2 excludes ignored python files below coverage source directories

Coverage reports retain the Git-visible eligible file boundary even when a root module makes the measured directory span the repository.

### 40.2.3 allows collection outside the configuration root

### 40.2.4 skips demo conftests before importing them

### 40.2.5 retains explicit nested owners inside demos

## 40.3 applying ownership consistently

### 40.3.1 requires stories for infrastructure and tools but not demo or harnesses

### 40.3.2 keeps demo and harness code in strict typechecking
