import { describe, expect, test } from './reports.ts';

describe('18.1 balancing file lists', () => {
  test('18.1.1 balances word counts and isolates large files', async ({ cz, logs, tempDir }) => {
    const wordCounts = { a: 30, b: 20, c: 10, large: 100 };
    for (const [name, words] of Object.entries(wordCounts)) await tempDir.write(name, 'word '.repeat(words));
    const listing = await tempDir.write('files.txt', 'a\nb\nc\nlarge\n');
    await cz.run('chunk-files', listing, '--chunks', '2', '--isolate-min-words', '100', '--json');
    expect(logs).toHaveLogged(/"word_count": 30/u);
    expect(logs).toHaveLogged(/"isolated": true/u);
    expect(logs).toHaveLogged(/"word_count": 100/u);
  });

  test('18.1.2 caps empty buckets and derives the chunk count from target words', async ({ cz, logs, tempDir }) => {
    const wordCount = 20;
    await tempDir.write('a', 'word '.repeat(wordCount));
    const listing = await tempDir.write('files.txt', 'a\n');
    await cz.run('chunk-files', listing, '--chunks', '10');
    expect(logs).toHaveLogged('Chunk 1: 1 file(s), 20 words\n  a');
    await cz.run('chunk-files', listing, '--target-words', '10');
    expect(logs).not.toHaveLogged(/Chunk 2/u);
  });

  test('18.1.3 rejects empty input conflicting options and unreadable files', async ({ cz, tempDir }) => {
    const empty = await tempDir.write('empty', '\n');
    await expect(cz.run('chunk-files', empty)).rejects.toThrow('no files given');
    await expect(cz.run('chunk-files', empty, '--chunks', '2', '--target-words', '10')).rejects.toThrow(
      'use --chunks or --target-words',
    );
    const missing = await tempDir.write('files.txt', 'absent\n');
    await expect(cz.run('chunk-files', missing)).rejects.toThrow('ENOENT');
  });
});
