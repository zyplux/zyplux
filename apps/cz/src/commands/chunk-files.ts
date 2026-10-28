import { ensure } from '@zyplux/util/assert';
import { readFileSync } from 'node:fs';
import { readFile } from 'node:fs/promises';

import type { InferValue } from '#optique';

import { argument, command, constant, integer, message, object, option, optional, string, withDefault } from '#optique';

const DEFAULT_TARGET_WORDS = 3500;
const DEFAULT_ISOLATE_WORDS = 2500;
const JSON_INDENT = 2;

const fileListArgument = withDefault(argument(string({ metavar: 'FILE_LIST' })), '-');
const chunksOption = optional(option('--chunks', integer({ min: 1 })));
const targetOption = optional(option('--target-words', integer({ min: 1 })));
const isolateOption = withDefault(option('--isolate-min-words', integer({ min: 1 })), DEFAULT_ISOLATE_WORDS);
const chunkParser = object({
  chunks: chunksOption,
  command: constant('chunk-files' as const),
  fileList: fileListArgument,
  isolateWords: isolateOption,
  json: option('--json'),
  targetWords: targetOption,
});
export const chunkFilesCommand = command('chunk-files', chunkParser, {
  brief: message`Balance file lists into word-count chunks and isolate large files.`,
});

export const runChunkFiles = async ({
  chunks,
  fileList,
  isolateWords,
  json,
  targetWords,
}: InferValue<typeof chunkFilesCommand>) => {
  type Chunk = { files: string[]; isolated: boolean; word_count: number };
  ensure(chunks === undefined || targetWords === undefined, 'use --chunks or --target-words');
  const source = fileList === '-' ? readFileSync(0, 'utf8') : await readFile(fileList, 'utf8');
  const files = source
    .split(/\r?\n/u)
    .map(file => file.trim())
    .filter(Boolean);
  ensure(files.length > 0, 'no files given');
  const measured = await Promise.all(
    files.map(async file => {
      const content = await readFile(file, 'utf8');
      return { file, words: content.match(/\S+/gu)?.length ?? 0 };
    }),
  );
  const total = measured.reduce((words, entry) => words + entry.words, 0);
  const count = chunks ?? Math.max(1, Math.round(total / (targetWords ?? DEFAULT_TARGET_WORDS)));
  const isolated = measured
    .filter(entry => entry.words >= isolateWords)
    .map(entry => ({ files: [entry.file], isolated: true, word_count: entry.words }));
  const shared = measured.filter(entry => entry.words < isolateWords).toSorted((a, b) => b.words - a.words);
  const balanced: Chunk[] = Array.from({ length: Math.min(count, shared.length) }, () => ({
    files: [],
    isolated: false,
    word_count: 0,
  }));
  for (const entry of shared) {
    const smallest = balanced.toSorted((a, b) => a.word_count - b.word_count)[0];
    ensure(smallest !== undefined, 'no balanced chunk for input file');
    smallest.files.push(entry.file);
    smallest.word_count += entry.words;
  }
  const grouped = [...balanced, ...isolated].map((chunk, index) => ({ index: index + 1, ...chunk }));
  console.log(
    json
      ? JSON.stringify(grouped, undefined, JSON_INDENT)
      : grouped
          .map(chunk =>
            [
              `Chunk ${chunk.index}${chunk.isolated ? ' (isolated)' : ''}: ${chunk.files.length} file(s), ${chunk.word_count} words`,
              ...chunk.files.map(file => `  ${file}`),
            ].join('\n'),
          )
          .join('\n\n'),
  );
};
