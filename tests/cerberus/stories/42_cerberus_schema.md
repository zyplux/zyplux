# 42. [Validating Cerberus configuration](test_42_cerberus_schema.py)

## 42.1 checking repository overrides

### 42.1.1 accepts partial overrides and missing configuration

### 42.1.2 reports unknown settings and invalid types

### 42.1.3 reports every schema problem

### 42.1.4 reports malformed toml

## 42.2 validating before other bites

### 42.2.1 stops before loading invalid overrides without rewriting them

### 42.2.2 has no configuration table or disable switch

### 42.2.3 validates the explicit configuration instead of the repository file

### 42.2.4 reports an unreadable explicit configuration
