# Airlock action

Set up locked workspace dependencies and plan or publish isolated release batches; follow the [Airlock release workflow](../airlock/README.md).

The action runs its own Python implementation in an isolated environment, installed from the action checkout and its `uv.lock`. Consumers select Airlock through the action reference and need no Airlock npm dependency.
