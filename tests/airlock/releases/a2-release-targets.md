# a2. [Discovering and resolving release targets](a2_release_targets_test.py)

## a2.1 loading release targets from the manifest

### a2.1.1 loads every declared target reading versions from json and toml manifests

### a2.1.2 reads project versions from parsed toml

### a2.1.3 infers package kinds from json and toml manifests

## a2.2 reading a manifest without a version

### a2.2.1 rejects manifests without a version

## a2.3 checking whether the ghcr image target is published

### a2.3.1 rejects finalized releases when their image cannot be accessed

### a2.3.2 authenticates private image probes and propagates registry failures

## a2.4 conforming the repo's own release manifest

### a2.4.1 loads a version for every target declared in airlock targets toml

## a2.5 resolving named targets

### a2.5.1 reads package names from manifests and derives tags from table names

### a2.5.2 honors package name overrides without changing the release tag

### a2.5.3 rejects malformed release declarations

### a2.5.4 rejects version sources outside the repository

### a2.5.5 reports unsupported manifest formats without a traceback

### a2.5.6 honors release tag overrides without changing target names
