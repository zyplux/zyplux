# 41. [Validating source classification](test_41_source_oracle.py)

## 41.1 configuring category globs

### 41.1.1 accepts bundled category defaults

### 41.1.2 overrides one category and retains all other defaults

### 41.1.3 overrides every category

Consumer overlays replace roots under `[source_oracle.types.<category>]` and retain the shared policies.

## 41.2 enforcing category limits

### 41.2.1 enforces shared nesting policies

Demo and docs scopes are terminal. Other categories cannot be declared inside them.

### 41.2.2 rejects equally specific conflicting categories

### 41.2.3 rejects consumer policy overrides

## 41.3 sharing the oracle

### 41.3.1 exposes the same classification to non python callers

The JSON CLI exposes the public classifier for CZ without duplicating category rules.
