# Airlock CLI tests

Run the release and package scenarios with pytest:

```sh
uv run pytest tests/airlock -o addopts=''
```

The tests invoke the Python CLI as a subprocess. Python fixtures provide temporary workspaces, command doubles and registry responses through a local server. `cli_runner.py` relays mocked commands and HTTP requests through one client without launching command subprocesses. Version preparation, dependency propagation and package archives also exercise native pnpm and uv commands in isolated workspaces.
