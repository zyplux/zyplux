# Airlock action

Plan isolated release batches and install locked workspace dependencies when publishing; follow the [Airlock release workflow](../airlock/README.md).

The action runs its own Python implementation in an isolated environment, installed from the action checkout and its `uv.lock`. Consumers select Airlock through the action reference and need no Airlock npm dependency.

Planning installs only uv and the publisher runtime. Publication additionally prepares the consuming repository's pnpm and Python workspaces.
