import { describe, expect, tempCwdTest as test } from '#fixtures';

const widgetShapeFile = `import { describe, expect, test } from 'vitest';

describe('widget formatting', () => {
  test('formats a widget', () => {
    expect(true).toBe(true);
  });
});
`;

const manifestParsingFile = `import { describe, expect, test } from 'vitest';

describe('other thing', () => {
  test('parses a manifest carefully', () => {
    expect(true).toBe(true);
  });
});
`;

const shapeValidationFile = `import { describe, expect, test } from 'vitest';

describe('shape validation', () => {
  test('validates a shape', () => {
    expect(true).toBe(true);
  });
});
`;

type ResolutionCase = [
  shape: string,
  files: Record<string, string>,
  filter: string,
  matchedFiles: string[],
  scopeToName: boolean,
];

const resolutionCases: ResolutionCase[] = [
  [
    '1 resolves a filter matching only a file path',
    { 'stories/7-widget-shape.test.ts': widgetShapeFile },
    '7-widget-shape',
    ['stories/7-widget-shape.test.ts'],
    false,
  ],
  [
    '2 resolves a filter matching only a test name',
    { 'stories/8-other-thing.test.ts': manifestParsingFile },
    'parses a manifest carefully',
    ['stories/8-other-thing.test.ts'],
    true,
  ],
  ['3 resolves a filter matching nothing', {}, 'nomatchxyz', [], false],
  [
    '4 resolves a filter matching both the path and a test name of the same file',
    { 'stories/9-shape.test.ts': shapeValidationFile },
    'shape',
    ['stories/9-shape.test.ts'],
    false,
  ],
];

describe('13.1 resolving a filter against real test files before running', () => {
  test.for(resolutionCases)('13.1.%s', async ([, files, filter, matchedFiles, scopeToName], { cz, shell, tempDir }) => {
    await tempDir.write('package.json', '{"scripts":{"test":"vitest run"}}');
    for (const [path, content] of Object.entries(files)) await tempDir.write(path, content);
    shell.on('bun run test', 'JS: ok');

    await cz.run('test', filter);

    const [command] = shell.commandsMatching('bun run test');
    if (matchedFiles.length > 0) {
      for (const file of matchedFiles) expect(command).toContain(file);
      if (scopeToName) expect(command).toContain(`-t ${filter}`);
      else expect(command).not.toContain('-t ');
    } else {
      expect(shell.commandsMatching('bun run test')).toEqual([]);
    }
  });
});

describe('13.2 unioning matches across multiple files', () => {
  test('13.2.1 runs every matched file together when different files match for different reasons', async ({
    cz,
    shell,
    tempDir,
  }) => {
    await tempDir.write('package.json', '{"scripts":{"test":"vitest run"}}');
    await tempDir.write(
      'stories/alpha-thing.test.ts',
      `import { describe, expect, test } from 'vitest';

describe('alpha section', () => {
  test('does nothing special', () => {
    expect(true).toBe(true);
  });
});
`,
    );
    await tempDir.write(
      'stories/beta-other.test.ts',
      `import { describe, expect, test } from 'vitest';

describe('beta section', () => {
  test('leaves a special-note in the log', () => {
    expect(true).toBe(true);
  });
});
`,
    );
    shell.on('bun run test', 'JS: ok');

    await cz.run('test', 'alpha-thing|special-note');

    const [command] = shell.commandsMatching('bun run test');
    expect(command).toContain('stories/alpha-thing.test.ts');
    expect(command).toContain('stories/beta-other.test.ts');
    expect(command).not.toContain('-t ');
  });
});
