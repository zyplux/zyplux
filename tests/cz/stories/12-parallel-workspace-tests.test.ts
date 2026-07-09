import type { TempDir } from '#fixtures';

import { describe, expect, tempCwdTest as test } from '#fixtures';

const writeJsWorkspace = async (tempDir: TempDir) => {
  await tempDir.write('package.json', '{"scripts":{"test":"vitest run"}}');
};

const writePyWorkspace = async (tempDir: TempDir) => {
  await tempDir.write('pyproject.toml', '[tool.pytest.ini_options]');
};

const writeBothWorkspaces = async (tempDir: TempDir) => {
  await writeJsWorkspace(tempDir);
  await writePyWorkspace(tempDir);
};

describe('12.1 running both workspaces in parallel', () => {
  test('12.1.1 runs vitest and pytest and prints the JS log before the Python log', async ({
    cz,
    logs,
    shell,
    tempDir,
  }) => {
    await writeBothWorkspaces(tempDir);
    shell.on('bun run test', 'JS: 12 passed');
    shell.on('uv run pytest', 'PY: 34 passed');

    await cz.run('test');

    expect(logs.logLines).toEqual(['JS: 12 passed', 'PY: 34 passed']);
  });

  test('12.1.2 fails when the JS tests fail, still printing both logs', async ({ cz, logs, shell, tempDir }) => {
    await writeBothWorkspaces(tempDir);
    shell.on('bun run test', { exitCode: 1, stdout: 'JS: 1 failed' });
    shell.on('uv run pytest', 'PY: 34 passed');

    await expect(cz.run('test')).rejects.toThrow('tests failed: JS');

    expect(logs.logLines).toEqual(['JS: 1 failed', 'PY: 34 passed']);
  });

  test('12.1.3 fails when the Python tests fail', async ({ cz, shell, tempDir }) => {
    await writeBothWorkspaces(tempDir);
    shell.on('bun run test', 'JS: 12 passed');
    shell.on('uv run pytest', { exitCode: 1, stdout: 'PY: 1 failed' });

    await expect(cz.run('test')).rejects.toThrow('tests failed: Python');
  });

  test('12.1.4 passes when pytest collects no tests', async ({ cz, shell, tempDir }) => {
    await writeBothWorkspaces(tempDir);
    shell.on('bun run test', 'JS: 12 passed');
    shell.on('uv run pytest', { exitCode: 5, stdout: 'PY: no tests ran' });

    await cz.run('test');
  });
});

describe('12.2 filtering by test name', () => {
  test('12.2.1 forwards the name filter and skips coverage on both runners', async ({ cz, shell, tempDir }) => {
    await writeBothWorkspaces(tempDir);
    shell.on('bun run test', 'JS: 2 passed');
    shell.on('uv run pytest', 'PY: 3 passed');

    await cz.run('test', 'parses the manifest');

    expect(shell.commandsMatching('bun run test')).toEqual([
      'bun run test -t parses the manifest --passWithNoTests --coverage.enabled=false 2>&1',
    ]);
    expect(shell.commandsMatching('uv run pytest')).toEqual(['uv run pytest --no-cov -k parses the manifest 2>&1']);
  });

  test('12.2.2 passes when the filter matches nothing in either workspace', async ({ cz, shell, tempDir }) => {
    await writeBothWorkspaces(tempDir);
    shell.on('bun run test', 'JS: no tests found');
    shell.on('uv run pytest', { exitCode: 5, stdout: 'PY: no tests ran' });

    await cz.run('test', 'nomatchxyz');
  });
});

describe('12.3 workspace detection', () => {
  test('12.3.1 runs only vitest when only package.json is present', async ({ cz, shell, tempDir }) => {
    await writeJsWorkspace(tempDir);
    shell.on('bun run test', 'JS: 12 passed');

    await cz.run('test');

    expect(shell.commands).toEqual(['bun run test 2>&1']);
  });

  test('12.3.2 runs only pytest when only pyproject.toml is present', async ({ cz, shell, tempDir }) => {
    await writePyWorkspace(tempDir);
    shell.on('uv run pytest', 'PY: 34 passed');

    await cz.run('test');

    expect(shell.commands).toEqual(['uv run pytest 2>&1']);
  });

  test('12.3.3 fails when neither workspace manifest is present', async ({ cz }) => {
    await expect(cz.run('test')).rejects.toThrow('no test workspace found');
  });
});
