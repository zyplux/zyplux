# Airlock action

The GitHub Actions entry point for the Airlock release CLI. Plan isolated release batches and install locked workspace dependencies when publishing; follow the [Airlock release workflow](../airlock/README.md).

The action runs its Python implementation in an isolated environment, installed from the action checkout and its `uv.lock`. The action reference selects the publisher version.

Planning installs only uv and the publisher runtime. Publication additionally prepares the consuming repository's pnpm and Python workspaces.
