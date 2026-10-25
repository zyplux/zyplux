# Airlock CLI tests

Run the release and package scenarios with pytest:

```sh
uv run pytest tests/airlock -o addopts=''
```

The tests invoke the CLI entry point inside each pytest worker, isolating arguments, environment, working directory and captured streams for each invocation. Python fixtures provide temporary workspaces, command doubles and registry responses through a local server. Version preparation, dependency propagation and package archives exercise native pnpm and uv commands in isolated workspaces. The installed-wheel checks run the CLI as a real subprocess.
