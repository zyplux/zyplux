import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-stray-pascal-const' });

const badSchemaName = [{ messageId: 'schemaName' }];
const strayPascal = [{ messageId: 'strayPascalConst' }];

describe('10.1 flagging misnamed zod schemas', () => {
  test('10.1.1 flags a z-rooted schema missing the Schema suffix or written in camelCase', ({ lintRule }) => {
    expect(lintRule('const User = z.object({ id: z.string() });')).toMatchObject(badSchemaName);
    expect(lintRule('const userSchema = z.object({ id: z.string() });')).toMatchObject(badSchemaName);
    expect(lintRule('const severity = z.union([a, b]);')).toMatchObject(badSchemaName);
  });

  test('10.1.2 flags a chained z-rooted schema and one behind a satisfies annotation', ({ lintRule }) => {
    expect(lintRule('const Profile = z.object({}).refine(Boolean);')).toMatchObject(badSchemaName);
    expect(lintRule('const ruleEntry = z.union([a, b]) satisfies z.ZodType<Entry>;')).toMatchObject(badSchemaName);
  });

  test('10.1.3 flags a schema from a custom factory, detected by type rather than z syntax', ({ lintRule }) => {
    const code = [
      "import { z } from 'zod';",
      'const makeSchema = () => z.object({ id: z.string() });',
      'const User = makeSchema();',
    ].join('\n');
    expect(lintRule(code)).toMatchObject(badSchemaName);
  });

  test('10.1.4 flags a schema composed off another schema', ({ lintRule }) => {
    const code = [
      "import { z } from 'zod';",
      'const BaseSchema = z.object({ id: z.string() });',
      'const Patch = BaseSchema.partial();',
    ].join('\n');
    expect(lintRule(code)).toMatchObject(badSchemaName);
  });

  test('10.1.5 flags a schema pulled out by destructuring', ({ lintRule }) => {
    const code = [
      "import { z } from 'zod';",
      'const registry = { User: z.object({ id: z.string() }) };',
      'const { User } = registry;',
    ].join('\n');
    expect(lintRule(code)).toMatchObject(badSchemaName);
  });
});

describe('10.2 flagging stray PascalCase consts', () => {
  test('10.2.1 flags a PascalCase const from an unrecognized factory or holding a plain object', ({ lintRule }) => {
    expect(lintRule('const Widget = makeWidget();')).toMatchObject(strayPascal);
    expect(lintRule('const Config = { retries: 3 };')).toMatchObject(strayPascal);
  });
});

describe('10.3 permitting well-named schemas', () => {
  test('10.3.1 allows PascalCase schemas with the Schema suffix, plain or chained', ({ lintRule }) => {
    expect(lintRule('const UserSchema = z.object({ id: z.string() });')).toHaveLength(0);
    expect(lintRule('const OcrJobRowSchema = z.looseObject({ id: z.string() });')).toHaveLength(0);
    expect(lintRule('const ResponseSchema = z.array(z.string()).min(1);')).toHaveLength(0);
  });

  test('10.3.2 allows a composed schema with a valid name', ({ lintRule }) => {
    const code = [
      "import { z } from 'zod';",
      'const BaseSchema = z.object({ id: z.string() });',
      'const PatchSchema = BaseSchema.partial();',
    ].join('\n');
    expect(lintRule(code)).toHaveLength(0);
  });

  test('10.3.3 allows a destructured schema renamed to a valid name', ({ lintRule }) => {
    const code = [
      "import { z } from 'zod';",
      'const registry = { User: z.object({ id: z.string() }) };',
      'const { User: UserSchema } = registry;',
    ].join('\n');
    expect(lintRule(code)).toHaveLength(0);
  });
});

describe('10.4 permitting non-schema names that are not PascalCase or not stray', () => {
  test('10.4.1 ignores camelCase values, UPPER_CASE constants, and non-schema destructured PascalCase', ({
    lintRule,
  }) => {
    expect(lintRule('const config = loadConfig();')).toHaveLength(0);
    expect(lintRule('const total = items.length;')).toHaveLength(0);
    expect(lintRule('const MAX_RETRIES = 3;')).toHaveLength(0);
    expect(lintRule('const { User } = registry;')).toHaveLength(0);
  });

  test('10.4.2 allows results of the default factory allowlist', ({ lintRule }) => {
    expect(lintRule('const ThemeContext = createContext(undefined);')).toHaveLength(0);
    expect(lintRule("const Route = createFileRoute('/posts')({});")).toHaveLength(0);
    expect(lintRule('const Field = forwardRef((props, ref) => null);')).toHaveLength(0);
    expect(lintRule('const Card = memo(BaseCard);')).toHaveLength(0);
  });

  test('10.4.3 allows a factory added through the allowed factories option', ({ lintRule }) => {
    expect(lintRule('const Banner = styled.div``;', { options: [{ allowedFactories: ['styled'] }] })).toHaveLength(0);
  });

  test('10.4.4 allows React components returning JSX or used as a JSX element in the same file', ({ lintRule }) => {
    expect(lintRule('const Greeting = () => <div>hi</div>;', { filename: 'react.tsx' })).toHaveLength(0);
    expect(
      lintRule('const Page = () => { if (loading) return <Spinner />; return <Content />; };', {
        filename: 'react.tsx',
      }),
    ).toHaveLength(0);
    expect(lintRule('const Card = wrap(Base);\nconst App = () => <Card />;', { filename: 'react.tsx' })).toHaveLength(
      0,
    );
  });
});
