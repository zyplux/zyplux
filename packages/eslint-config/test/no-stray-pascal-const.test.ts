import { noStrayPascalConst } from '#rules/no-stray-pascal-const';

import { typeAwareRuleTester } from './rule-tester';

typeAwareRuleTester.run('no-stray-pascal-const', noStrayPascalConst, {
  invalid: [
    {
      code: 'const User = z.object({ id: z.string() });',
      errors: [{ messageId: 'schemaName' }],
      name: 'z-rooted schema missing the Schema suffix',
    },
    {
      code: 'const userSchema = z.object({ id: z.string() });',
      errors: [{ messageId: 'schemaName' }],
      name: 'Schema suffix but camelCase, not PascalCase',
    },
    {
      code: 'const severity = z.union([a, b]);',
      errors: [{ messageId: 'schemaName' }],
      name: 'lowercase z-rooted building block',
    },
    {
      code: 'const Profile = z.object({}).refine(Boolean);',
      errors: [{ messageId: 'schemaName' }],
      name: 'chained z-rooted schema missing the suffix',
    },
    {
      code: 'const ruleEntry = z.union([a, b]) satisfies z.ZodType<Entry>;',
      errors: [{ messageId: 'schemaName' }],
      name: 'z-rooted schema behind a `satisfies` annotation',
    },
    {
      code: [
        "import { z } from 'zod';",
        'const makeSchema = () => z.object({ id: z.string() });',
        'const User = makeSchema();',
      ].join('\n'),
      errors: [{ messageId: 'schemaName' }],
      name: 'schema from a custom factory — detected by type, not by `z.` syntax',
    },
    {
      code: [
        "import { z } from 'zod';",
        'const BaseSchema = z.object({ id: z.string() });',
        'const Patch = BaseSchema.partial();',
      ].join('\n'),
      errors: [{ messageId: 'schemaName' }],
      name: 'schema composed off another schema (`.partial()`)',
    },
    {
      code: [
        "import { z } from 'zod';",
        'const registry = { User: z.object({ id: z.string() }) };',
        'const { User } = registry;',
      ].join('\n'),
      errors: [{ messageId: 'schemaName' }],
      name: 'schema pulled out by destructuring',
    },
    {
      code: 'const Widget = makeWidget();',
      errors: [{ messageId: 'strayPascalConst' }],
      name: 'PascalCase const from an unrecognized factory',
    },
    {
      code: 'const Config = { retries: 3 };',
      errors: [{ messageId: 'strayPascalConst' }],
      name: 'PascalCase const holding a plain object',
    },
  ],
  valid: [
    'const UserSchema = z.object({ id: z.string() });',
    'const OcrJobRowSchema = z.looseObject({ id: z.string() });',
    {
      code: 'const ResponseSchema = z.array(z.string()).min(1);',
      name: 'chained schema with a valid name',
    },
    {
      code: [
        "import { z } from 'zod';",
        'const BaseSchema = z.object({ id: z.string() });',
        'const PatchSchema = BaseSchema.partial();',
      ].join('\n'),
      name: 'composed schema with a valid name',
    },
    {
      code: [
        "import { z } from 'zod';",
        'const registry = { User: z.object({ id: z.string() }) };',
        'const { User: UserSchema } = registry;',
      ].join('\n'),
      name: 'destructured schema renamed to a valid name',
    },
    {
      code: 'const config = loadConfig();',
      name: 'camelCase non-zod value is ignored',
    },
    {
      code: 'const total = items.length;',
      name: 'camelCase member expression not rooted at z',
    },
    {
      code: 'const MAX_RETRIES = 3;',
      name: 'UPPER_CASE constant is not PascalCase',
    },
    {
      code: 'const { User } = registry;',
      name: 'destructured PascalCase whose value is not a schema',
    },
    {
      code: 'const ThemeContext = createContext(undefined);',
      name: 'React context factory',
    },
    {
      code: "const Route = createFileRoute('/posts')({});",
      name: 'TanStack curried route factory',
    },
    {
      code: 'const Field = forwardRef((props, ref) => null);',
      name: 'forwardRef-wrapped component',
    },
    {
      code: 'const Card = memo(BaseCard);',
      name: 'memo-wrapped component',
    },
    {
      code: 'const Banner = styled.div``;',
      name: 'factory added through the allowedFactories option',
      options: [{ allowedFactories: ['styled'] }],
    },
    {
      code: 'const Greeting = () => <div>hi</div>;',
      filename: 'react.tsx',
      name: 'arrow component returning JSX',
    },
    {
      code: 'const Page = () => { if (loading) return <Spinner />; return <Content />; };',
      filename: 'react.tsx',
      name: 'component returning JSX from a branch',
    },
    {
      code: 'const Card = wrap(Base);\nconst App = () => <Card />;',
      filename: 'react.tsx',
      name: 'PascalCase const used as a JSX element in the same file',
    },
  ],
});
