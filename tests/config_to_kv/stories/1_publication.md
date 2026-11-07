# 1 Config publication

## 1.1 Publishes validator snapshot without reading secret values

A first publication writes the validator snapshot and config commit to KV.

## 1.2 Rejects unbound credentials before publication

Deployed Workers must have matching environment-specific secret bindings and a compatible validator.

## 1.3 Skips unchanged snapshots

An unchanged revision causes no Worker inspection or KV write.
