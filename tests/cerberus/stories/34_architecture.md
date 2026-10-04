# 34. [Enforcing shared package architecture](test_34_architecture.py)

## 34.1 public exports

### 34.1.1 accepts library export families and conditional or asset entries

### 34.1.2 rejects mixed exports misnamed entries and published key drift

### 34.1.3 preserves framework application roots and binary only apps

## 34.2 application keepers

### 34.2.1 checks one keeper within each independent application scope

### 34.2.2 rejects invalid keeper surfaces and second contract only packages

### 34.2.3 rejects unknown packages and overlapping application scopes

## 34.3 dependency direction

### 34.3.1 dependency direction checks each manifest dependency category

### 34.3.2 rejects unknown dependency policy packages

## 34.4 project references

### 34.4.1 project references match compiled dependencies once

### 34.4.2 project references resolve jsonc and inherited workspace configs

### 34.4.3 project references check projects with external compiler settings

## 34.5 side effect declarations

### 34.5.1 side effect metadata preserves registration modules

### 34.5.2 pure libraries may declare no side effects

## 34.6 Worker runtime reachability

### 34.6.1 workers follow runtime imports and ignore type edges or text

### 34.6.2 workers resolve local aliases and package import maps

### 34.6.3 worker scan reports missing first party entries and visible external gaps

### 34.6.4 workers follow inherited aliases and export arrays

### 34.6.5 workers respect blocked exports and default condition order

### 34.6.6 workers resolve child paths relative to their declaring config

## 34.7 validating architecture configuration

### 34.7.1 rejects invalid architecture declarations
