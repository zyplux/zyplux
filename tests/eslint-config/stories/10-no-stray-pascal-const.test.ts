import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-stray-pascal-const' });

type SchemaCase = [shape: string, codes: string[]];

describe('10.1 flagging misnamed zod schemas', () => {
  const cases: SchemaCase[] = [
    [
      '1 flags a z-rooted schema missing the Schema suffix or written in camelCase',
      [
        'const User = z.object({ id: z.string() });',
        'const userSchema = z.object({ id: z.string() });',
        'const severity = z.union([a, b]);',
      ],
    ],
    [
      '2 flags a chained z-rooted schema and one behind a satisfies annotation',
      [
        'const Profile = z.object({}).refine(Boolean);',
        'const ruleEntry = z.union([a, b]) satisfies z.ZodType<Entry>;',
      ],
    ],
    [
      '3 flags a schema from a custom factory, detected by type rather than z syntax',
      [
        [
          "import { z } from 'zod';",
          'const makeSchema = () => z.object({ id: z.string() });',
          'const User = makeSchema();',
        ].join('\n'),
      ],
    ],
    [
      '4 flags a schema composed off another schema',
      [
        [
          "import { z } from 'zod';",
          'const BaseSchema = z.object({ id: z.string() });',
          'const Patch = BaseSchema.partial();',
        ].join('\n'),
      ],
    ],
    [
      '5 flags a schema pulled out by destructuring',
      [
        [
          "import { z } from 'zod';",
          'const registry = { User: z.object({ id: z.string() }) };',
          'const { User } = registry;',
        ].join('\n'),
      ],
    ],
  ];

  test.for(cases)('10.1.%s', ([, codes], { expectEachToReport, lintRule }) => {
    expectEachToReport(lintRule, codes, 'schemaName');
  });
});

describe('10.2 flagging stray PascalCase consts', () => {
  test('10.2.1 flags a PascalCase const from an unrecognized factory or holding a plain object', ({ lintRule }) => {
    expect(lintRule('const Widget = makeWidget();')).toReport('strayPascalConst');
    expect(lintRule('const Config = { retries: 3 };')).toReport('strayPascalConst');
  });
});

describe('10.3 permitting well-named schemas', () => {
  const cases: SchemaCase[] = [
    [
      '1 allows PascalCase schemas with the Schema suffix, plain or chained',
      [
        'const UserSchema = z.object({ id: z.string() });',
        'const OcrJobRowSchema = z.looseObject({ id: z.string() });',
        'const ResponseSchema = z.array(z.string()).min(1);',
      ],
    ],
    [
      '2 allows a composed schema with a valid name',
      [
        [
          "import { z } from 'zod';",
          'const BaseSchema = z.object({ id: z.string() });',
          'const PatchSchema = BaseSchema.partial();',
        ].join('\n'),
      ],
    ],
    [
      '3 allows a destructured schema renamed to a valid name',
      [
        [
          "import { z } from 'zod';",
          'const registry = { User: z.object({ id: z.string() }) };',
          'const { User: UserSchema } = registry;',
        ].join('\n'),
      ],
    ],
  ];

  test.for(cases)('10.3.%s', ([, codes], { expectEachToReportNothing, lintRule }) => {
    expectEachToReportNothing(lintRule, codes);
  });
});

type NonStrayCase = [shape: string, entries: [code: string, options?: RuleLintOptions][]];
type RuleLintOptions = { filename?: string; options?: unknown[] };

describe('10.4 permitting non-schema names that are not PascalCase or not stray', () => {
  const cases: NonStrayCase[] = [
    [
      '1 ignores camelCase values, UPPER_CASE constants, and non-schema destructured PascalCase',
      [
        ['const config = loadConfig();'],
        ['const total = items.length;'],
        ['const MAX_RETRIES = 3;'],
        ['const { User } = registry;'],
      ],
    ],
    [
      '2 allows results of the default factory allowlist',
      [
        ['const ThemeContext = createContext(undefined);'],
        ["const Route = createFileRoute('/posts')({});"],
        ['const Field = forwardRef((props, ref) => null);'],
        ['const Card = memo(BaseCard);'],
      ],
    ],
    [
      '3 allows a factory added through the allowed factories option',
      [['const Banner = styled.div``;', { options: [{ allowedFactories: ['styled'] }] }]],
    ],
    [
      '4 allows React components returning JSX or used as a JSX element in the same file',
      [
        ['const Greeting = () => <div>hi</div>;', { filename: 'react.tsx' }],
        ['const Page = () => { if (loading) return <Spinner />; return <Content />; };', { filename: 'react.tsx' }],
        ['const Card = wrap(Base);\nconst App = () => <Card />;', { filename: 'react.tsx' }],
      ],
    ],
  ];

  test.for(cases)('10.4.%s', ([, entries], { lintRule }) => {
    for (const [code, options] of entries) expect(lintRule(code, options)).toReportNothing();
  });
});
