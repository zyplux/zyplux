import { describe, expect, test } from './workspace.ts';

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
});
