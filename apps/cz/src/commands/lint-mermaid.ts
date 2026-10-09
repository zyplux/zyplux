import { ensure } from '@zyplux/util/assert';
import { Parser } from 'commonmark';
import { glob, readFile } from 'node:fs/promises';

import { command, constant, message, object } from '#optique';

export const lintMermaidCommand = command('lint-mermaid', object({ command: constant('lint-mermaid' as const) }), {
  brief: message`Check Mermaid diagrams in Markdown files under the current directory.`,
});

type MermaidFence = { source: string; startLine: number };

const listFences = (markdown: string) => {
  const fences: MermaidFence[] = [];
  const walker = new Parser().parse(markdown).walker();
  for (let visit = walker.next(); visit !== null; visit = walker.next()) {
    const node = visit.node;
    if (node.type === 'code_block' && node.info?.split(/\s+/u, 1)[0] === 'mermaid') {
      fences.push({ source: node.literal ?? '', startLine: node.sourcepos[0][0] });
    }
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
