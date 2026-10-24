# 2. [Discovering and resolving release targets](test_2_release_targets.py)

## 2.1 loading release targets from the manifest

### 2.1.1 loads every declared target reading versions from json and regex sources

## 2.2 reading a version whose regex does not match its source file

### 2.2.1 rejects reading a version whose regex does not match the file

## 2.3 checking whether the ghcr image target is published

### 2.3.1 rejects finalized releases when their image cannot be accessed

### 2.3.2 authenticates private image probes and propagates registry failures

## 2.4 conforming the repo's own release manifest

### 2.4.1 loads a version for every target declared in airlock targets toml

## 2.5 resolving named targets

### 2.5.1 derives labels from the configured scope and tags from table names

### 2.5.2 honors explicit labels without changing the derived tag prefix

### 2.5.3 rejects malformed release declarations
