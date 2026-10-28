# Airlock action

The GitHub Actions entry point for the Airlock release CLI. Plan isolated release batches and install locked workspace dependencies when publishing; follow the [Airlock release workflow](../airlock/README.md).

The action runs its Python implementation in an isolated environment, installed from the action checkout and its `uv.lock`. The action reference selects the publisher version.

Both commands use the shared package-manager action to prepare cached tools. Planning installs only the publisher runtime; publication additionally prepares the consuming repository's pnpm and Python workspaces.
