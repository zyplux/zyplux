# 4. [Parsing TOML into schema-validated values](4-toml.test.ts)

## 4.1 parsing toml text against a schema

>`parseToml(text, schema)` runs `Bun.TOML.parse` on the text and pipes the result through a Zod schema, so callers get a fully-typed value back or an exception describing exactly what was wrong with the input.

1. returns the schema validated value for well formed toml
2. throws on malformed toml syntax
3. throws a zod error when the parsed value does not match the schema

## 4.2 parsing toml text without throwing

>`tryParseToml(text, schema)` wraps `parseToml` so callers who only want a best-effort value can treat any failure — bad syntax or a schema mismatch — the same way: as `undefined`, with no exception to catch.

1. returns the schema validated value for well formed toml
2. returns undefined instead of throwing on malformed toml syntax
3. returns undefined instead of throwing when the parsed value does not match the schema

## 4.3 confining outcome assertions to their own failure mode

>`toParseTomlAs` distinguishes a genuine TOML syntax error from a schema mismatch — a schema-invalid parse must not satisfy a `syntaxError` assertion just because it also throws.

### 4.3.1 a schema mismatch does not satisfy a syntaxError assertion
