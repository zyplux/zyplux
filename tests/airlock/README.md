# Airlock CLI tests

Run the release and package scenarios with pytest:

```sh
uv run pytest tests/airlock -o addopts=''
```

The tests invoke the TypeScript CLI as a subprocess. Python fixtures provide temporary workspaces, command doubles and registry responses through a local server. `preload.ts` connects Node's HTTP and timer boundaries to those fixtures. Version preparation, dependency propagation and package archives also exercise native pnpm and uv commands in isolated workspaces.
