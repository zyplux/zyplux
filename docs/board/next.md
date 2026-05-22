# Next

## Unified config

- unify all the config files into a single install.toml file
- should allow to list all the packages from all the package managers or configs
- each entry should indicate which installer it requires
- should allow to group entries as one (for apt packages etc.) for same installer type
- should allow not only to install apt/uv/cargo packages but also apt repos, urls - everything
- should support depends_on flag to force sequential execution, otherwise everything should run in parallel
- packages that require installer should automatically depend on installer by that name (so no need to add depends_on)
- each installation to follow same idempotent pattern:

  ```text
  if not installed
    install
  else upgrade
  ```

- refactor code to cetralize idempotency logic. In other words installes should just implement interface to list, upgrade, install (in future also uninstall and show-latest potentially) etc. Orchestrator then just executes over the config file, manages dependencies and parallelism, accumulates report for the final print etc.
- we should also be able to run everything with --list flag to just show the current state of every item (version or information)
- generate the unified install.toml first and confirm it with user prior to making python refactor
- overall this tool should become a universal recipe runner similar to the ansible
