import { ensure } from '@zyplux/util/assert';
import { glob, readFile } from 'node:fs/promises';

import { command, constant, message, object } from '#optique';

export const lintMermaidCommand = command('lint-mermaid', object({ command: constant('lint-mermaid' as const) }), {
  brief: message`Check Mermaid diagrams in Markdown files under the current directory.`,
});

type MermaidFence = { source: string; startLine: number };

const FENCE_OPEN = /^\s*```mermaid\s*$/;
const FENCE_CLOSE = /^\s*```\s*$/;

const listFences = (markdown: string) => {
  const fences: MermaidFence[] = [];
  let openedAtLine: number | undefined;
  let fenceLines: string[] = [];
  for (const [index, line] of markdown.split('\n').entries()) {
    if (openedAtLine === undefined) {
      if (FENCE_OPEN.test(line)) {
        openedAtLine = index + 1;
        fenceLines = [];
      }
    } else if (FENCE_CLOSE.test(line)) {
      fences.push({ source: fenceLines.join('\n'), startLine: openedAtLine });
      openedAtLine = undefined;
    } else {
      fenceLines.push(line);
    }
  }
  if (openedAtLine !== undefined) {
    fences.push({ source: fenceLines.join('\n'), startLine: openedAtLine });
  }
  return fences;
};

const findParseError = async (source: string, parse: typeof import('mermaid').default.parse) => {
  try {
    await parse(source);
    return;
  } catch (error) {
    return error instanceof Error ? error.message : JSON.stringify(error);
  }
};

const lintMarkdown = async (parse: typeof import('mermaid').default.parse) => {
  const failures: string[] = [];
  let fenceCount = 0;
  const markdownPaths = glob('**/*.md', { exclude: ['**/logs/**', '**/node_modules/**'] });
  for await (const markdownPath of markdownPaths) {
    const markdown = await readFile(markdownPath, 'utf8');
    for (const fence of listFences(markdown)) {
      fenceCount += 1;
      const parseError = await findParseError(fence.source, parse);
      if (parseError !== undefined) failures.push(`${markdownPath}:${fence.startLine}\n${parseError}`);
    }
  }
  ensure(
    failures.length === 0,
    `${failures.length} of ${fenceCount} mermaid diagrams failed to parse:

${failures.join('\n\n')}`,
  );
  console.log(`All ${fenceCount} mermaid diagrams parse.`);
};

export const runLintMermaid = async () => {
  const { GlobalRegistrator } = await import('@happy-dom/global-registrator');
  // Mermaid needs DOM globals before import, including for syntax validation.
  GlobalRegistrator.register();
  try {
    const { default: mermaid } = await import('mermaid');
    await lintMarkdown(mermaid.parse);
  } finally {
    await GlobalRegistrator.unregister();
  }
};
