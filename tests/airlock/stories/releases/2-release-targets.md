# 2. [Discovering and resolving release targets](test_2_release_targets.py)

## 2.1 loading release targets from the manifest

### 2.1.1 loads every declared target reading versions from json and toml manifests

### 2.1.2 reads project versions from parsed toml

### 2.1.3 infers package kinds from json and toml manifests

## 2.2 reading a manifest without a version

### 2.2.1 rejects manifests without a version

## 2.3 checking whether the ghcr image target is published

### 2.3.1 rejects finalized releases when their image cannot be accessed

### 2.3.2 authenticates private image probes and propagates registry failures

## 2.4 conforming the repo's own release manifest

### 2.4.1 loads a version for every target declared in airlock targets toml

## 2.5 resolving named targets

### 2.5.1 reads package names from manifests and derives tags from table names

### 2.5.2 honors package name overrides without changing the release tag

### 2.5.3 rejects malformed release declarations

### 2.5.4 rejects version sources outside the repository

### 2.5.5 reports unsupported manifest formats without a traceback

### 2.5.6 honors release tag overrides without changing target names
