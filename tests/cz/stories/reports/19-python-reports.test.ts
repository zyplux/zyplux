import { describe, expect, test } from './reports.ts';

describe('19.1 delegating Python work to Clipy', () => {
  test('19.1.1 passes stats options to the installed Python helper', async ({ cz, shell }) => {
    shell.on('uv run clipy stats', '');
    await cz.run('stats', 'apps/api', '--out', 'reports/api.md', '--title', 'API');
    expect(shell.commands).toContain('uv run clipy stats apps/api --out reports/api.md --title API');
  });

  test('19.1.2 defaults to the current directory and preserves helper failures', async ({ cz, shell }) => {
    shell.on('uv run clipy stats', '');
    await cz.run('stats');
    expect(shell.commands).toContain('uv run clipy stats .');
    shell.on('uv run clipy stats', { exitCode: 1, stdout: 'measurement failed' });
    await expect(cz.run('stats')).rejects.toThrow('command failed with exit code 1');
  });
});
