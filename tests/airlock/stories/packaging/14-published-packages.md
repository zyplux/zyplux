# 14. [Publishing installable release packages](test_14_published_packages.py)

## 14.1 packing release targets

### 14.1.1 passes publint for every built npm archive

### 14.1.2 installs airlock from its python wheel

### 14.1.3 starts cerberus with its declared runtime dependencies

Every npm target in `airlock_targets.toml` is built and packed with pnpm. Each package's `prepack` script runs Publint over the publishable archive with pnpm's manifest transformations applied. Warnings and errors prevent packing.

Airlock builds a Python wheel and source archive. The wheel must install in an isolated environment and expose the release CLI.

Cerberus starts from an isolated wheel installation, with its workspace Airlock dependency supplied as a built wheel.
