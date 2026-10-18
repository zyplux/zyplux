import { describe, expect, test } from './rules.ts';

test.override({ ruleName: 'no-function-scoped-schema' });

describe('19.1 reusing schemas independent of function inputs', () => {
  test.for([
    "import * as z from 'zod'; const minimum = 1; const read = () => z.string().min(minimum);",
    "import * as z from 'zod'; const minimum: number | undefined = 1; const read = () => z.string().min(minimum ?? 0);",
    "import * as z from 'zod'; const read = (raw: unknown) => z.string().parse(raw);",
    "import * as z from 'zod'; const read = () => z.object({ name: z.string() }).optional();",
    "import { string as text } from 'zod'; const read = () => text().min(1);",
    "import { PackageJsonSchema } from '@zyplux/util/contracts'; const read = () => PackageJsonSchema.array();",
    "import * as z from 'zod'; const read = () => z.string().refine(value => value.length > 1);",
    "import * as z from 'zod'; const read = () => { const schema = z.array(z.string()); return schema; };",
    "import * as z from 'zod'; const read = () => z.lazy(() => z.string());",
    "import * as z from 'zod'; const reuse = (schema: z.ZodString) => schema; const read = () => reuse(z.string());",
  ])('19.1.1 reports one schema construction: %s', (code, { lintRule }) => {
    expect(lintRule(code)).toReport('hoistSchema');
  });
});

describe('19.2 permitting reusable schemas and input-dependent factories', () => {
  test.for([
    "import * as z from 'zod'; const Schema = z.string(); const read = (raw: unknown) => Schema.parse(raw);",
    "import * as z from 'zod'; const build = (minimum: number) => z.string().min(minimum);",
    "import * as z from 'zod'; const build = (limit: number) => z.string().refine(value => value.length < limit);",
    "import * as z from 'zod'; const build = (schema: z.ZodString) => schema.array();",
    "import * as z from 'zod'; const build = () => { const limit = Math.random(); return z.string().min(limit); };",
    "import * as z from 'zod'; const build = () => z.number().default(Math.random());",
    "import * as z from 'zod'; const build = () => z.date().default(new Date());",
    "import * as z from 'zod'; class Builder { limit = 1; build() { return z.string().min(this.limit); } }",
    "import * as z from 'zod'; const settings = { minimum: 1 }; const build = () => z.string().min(settings.minimum);",
    "import * as z from 'zod'; import { exitCode } from 'node:process'; const build = () => z.literal(exitCode);",
    "import * as z from 'zod'; let Schema = z.string(); const build = () => Schema.array();",
    "import * as z from 'zod'; const build = () => z.string().min(unresolved);",
    "import * as z from 'zod'; let limit = 1; const build = () => z.string().min(limit);",
    "import * as z from 'zod'; const Schema = z.lazy(() => z.object({ name: z.string() }));",
    "import * as z from 'zod'; const Schema = z.object({ get children() { return z.array(Schema); } });",
    "import * as z from 'zod'; const Schema = z.string(); const findSchema = () => Schema; const read = () => findSchema();",
    'const other = { string: () => "text" }; const read = () => other.string();',
    "import * as z from 'zod'; const Schema = z.string(); const read = () => z.toJSONSchema(Schema);",
  ])('19.2.1 permits schema ownership: %s', (code, { lintRule }) => {
    expect(lintRule(code)).toReportNothing();
  });
});
