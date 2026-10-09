import { describe, expect, test as workspaceTest } from './workspace.ts';

const test = workspaceTest.extend<{ markdownSetup: undefined }>({
  markdownSetup: [
    async ({ markdownRepo }, use) => {
      await markdownRepo.init();
      await use(undefined);
    },
    { auto: true },
  ],
});

describe('16.1 checking Markdown diagrams', () => {
  test('16.1.1 checks diagrams in nested Markdown files and ignores dependency and log folders', async ({
    cz,
    logs,
    tempDir,
  }) => {
    await tempDir.write('docs/guide.md', '# Guide\n\n```mermaid\nflowchart LR\n  A --> B\n```\n');
    await tempDir.write('docs/plain.md', '# Notes\n\n```text\nnot a diagram\n```\n');
    await tempDir.write('node_modules/package/README.md', '```mermaid\ninvalid\n```');
    await tempDir.write('logs/run.md', '```mermaid\ninvalid\n```');

    await cz.run('lint-mermaid');

    expect(logs).toHaveLogged('All 1 mermaid diagrams parse.');
  });

  test('16.1.2 reports each invalid diagram with its file and opening line', async ({ cz, tempDir }) => {
    await tempDir.write('broken.md', '# Broken\n\n```mermaid\ninvalid diagram\n```\n\n```mermaid\nalso invalid');

    await expect(cz.run('lint-mermaid')).rejects.toThrow(
      /2 of 2 mermaid diagrams failed to parse:[\s\S]*broken.md:3[\s\S]*broken.md:7/u,
    );
  });

  test('16.1.3 succeeds with no diagrams and can run again after a parse failure', async ({ cz, logs, tempDir }) => {
    await cz.run('lint-mermaid');
    expect(logs).toHaveLogged('All 0 mermaid diagrams parse.');

    await tempDir.write('guide.md', '```mermaid\ninvalid\n```');
    await expect(cz.run('lint-mermaid')).rejects.toThrow('1 of 1 mermaid diagrams failed to parse');
    await tempDir.write('guide.md', '```mermaid\nsequenceDiagram\n  Alice->>Bob: Hello\n```');
    await cz.run('lint-mermaid');
    expect(logs).toHaveLogged('All 1 mermaid diagrams parse.');
  });

  test('16.1.4 checks tilde and longer backtick fences inside Markdown containers', async ({ cz, logs, tempDir }) => {
    await tempDir.write(
      'guide.md',
      '# Guide\r\n\r\n~~~ mermaid title\r\nflowchart LR\r\n  A --> B\r\n~~~~\r\n\r\n> ````mermaid\r\n> sequenceDiagram\r\n>   Alice->>Bob: Hello\r\n> `````\r\n\r\n- Diagram:\r\n\r\n  ~~~~mermaid\r\n  flowchart LR\r\n    A --> B',
    );

    await cz.run('lint-mermaid');

    expect(logs).toHaveLogged('All 3 mermaid diagrams parse.');
  });

  test('16.1.5 reports invalid diagrams across fence delimiters with their original lines', async ({ cz, tempDir }) => {
    await tempDir.write('broken.md', '# Broken\n\n~~~mermaid\ninvalid\n~~~\n\n> ````mermaid\n> invalid\n> ````');

    await expect(cz.run('lint-mermaid')).rejects.toThrow(
      /2 of 2 mermaid diagrams failed to parse:[\s\S]*broken.md:3[\s\S]*broken.md:7/u,
    );
  });

  test('16.1.6 keeps shorter and mismatched delimiters inside the diagram', async ({ cz, tempDir }) => {
    await tempDir.write('broken.md', '````mermaid\nflowchart LR\n  A --> B\n```\n~~~\n````');

    await expect(cz.run('lint-mermaid')).rejects.toThrow('1 of 1 mermaid diagrams failed to parse');
  });

  test('16.1.7 ignores fence examples inside other code blocks', async ({ cz, logs, tempDir }) => {
    await tempDir.write('guide.md', '````text\n```mermaid\ninvalid\n```\n````\n\n    ~~~mermaid\n    invalid\n    ~~~');

    await cz.run('lint-mermaid');

    expect(logs).toHaveLogged('All 0 mermaid diagrams parse.');
  });

  test('16.1.8 checks hidden files and directories while excluding dependency and log trees', async ({
    cz,
    logs,
    markdownRepo,
    tempDir,
  }) => {
    await tempDir.write('.github/copilot-instructions.md', '~~~mermaid\ninvalid\n~~~');
    await tempDir.write('docs/.agents/nested/.guide.md', '````mermaid\ninvalid\n````');
    await tempDir.write('.agents/node_modules/package/README.md', '```mermaid\ninvalid\n```');
    await tempDir.write('.github/logs/run.md', '```mermaid\ninvalid\n```');
    await tempDir.write('.claude/worktrees/old/docs.md', '```mermaid\ninvalid\n```');
    markdownRepo.track('.github/copilot-instructions.md');

    const lintRun = cz.run('lint-mermaid');
    await expect(lintRun).rejects.toThrow('2 of 2 mermaid diagrams failed to parse');
    await expect(lintRun).rejects.toThrow('.github/copilot-instructions.md:1');
    await expect(lintRun).rejects.toThrow('docs/.agents/nested/.guide.md:1');

    await tempDir.write('.github/copilot-instructions.md', '~~~mermaid\nflowchart LR\n  A --> B\n~~~');
    await tempDir.write('docs/.agents/nested/.guide.md', '````mermaid\nflowchart LR\n  A --> B\n````');
    await cz.run('lint-mermaid');
    expect(logs).toHaveLogged('All 2 mermaid diagrams parse.');
  });

  test('16.1.9 skips deleted tracked Markdown files', async ({ cz, logs, markdownRepo, tempDir }) => {
    await tempDir.write('removed.md', '```mermaid\ninvalid\n```');
    markdownRepo.track('removed.md');
    await markdownRepo.remove('removed.md');

    await cz.run('lint-mermaid');

    expect(logs).toHaveLogged('All 0 mermaid diagrams parse.');
  });
});
