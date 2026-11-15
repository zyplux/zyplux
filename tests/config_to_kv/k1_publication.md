# k1. [Config publication](k1_publication_test.py)

## k1.1 Publishes validator snapshot without reading secret values

A first publication writes the validator snapshot and config commit to KV.

## k1.2 Rejects unbound credentials before publication

Deployed Workers must have matching environment-specific secret bindings and a compatible validator.

## k1.3 Skips unchanged snapshots

An unchanged revision skips the KV write and retries declared bootstrap notifications.

## k1.4 Bootstrap follows successful publication
