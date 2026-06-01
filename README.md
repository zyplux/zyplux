# @totvibe/eslint-config

Shared ESLint flat config and custom rules for totvibe projects. Ships TypeScript source — consumed directly under Bun.

## Install

```sh
bun add -D @totvibe/eslint-config eslint typescript
```

## Use

`eslint.config.ts`:

```ts
import { totvibe } from '@totvibe/eslint-config';

export default totvibe({ tsconfigRootDir: import.meta.dirname });
```

Frontend (React + TanStack Router):

```ts
import { totvibe } from '@totvibe/eslint-config';

export default totvibe({
  react: true,
  tanstack: true,
  tsconfigRootDir: import.meta.dirname,
});
```

### Options

| Option             | Default                            | Description                                                                           |
| ------------------ | ---------------------------------- | ------------------------------------------------------------------------------------- |
| `react`            | `false`                            | Enable `eslint-plugin-react` + React Hooks rules                                      |
| `tanstack`         | `false`                            | Enforce kebab-case filenames under `routes/`                                          |
| `tsconfigRootDir`  | `process.cwd()`                    | Root for typed linting (`projectService`)                                             |
| `reactFiles`       | `['**/src/**/*.{ts,tsx}']`         | Globs the React rules apply to                                                        |
| `reactVersion`     | `'detect'`                         | React version for `eslint-plugin-react`; pin it (e.g. `'19.0'`) where detection fails |
| `filenameCase`     | kebab (camel/kebab/pascal w/react) | Allowed `unicorn/filename-case` cases, e.g. `{ camelCase: true, pascalCase: true }`   |
| `nonDomReactFiles` | `[]`                               | Globs on a non-DOM renderer (OpenTUI/Ink/r3f); turns off `react/no-unknown-property`  |
| `ignores`          | `[]`                               | Extra ignore globs appended to the defaults                                           |

`reactVersion` matters in a workspace where `react` is a per-app dependency: `'detect'` resolves from the lint working directory, finds nothing at the monorepo root, warns, and falls back nondeterministically — pin the version to silence it. `filenameCase` defaults to camel/kebab/pascal when `react: true` (component files are conventionally Pascal) and to unicorn's kebab-only otherwise. `nonDomReactFiles` requires `react: true`.

The custom `@totvibe` rules (`no-inferrable-return-type`, `no-type-predicate`, `no-zod-custom`, `prefer-arrow-functions`) are bundled and always on.

### Interactions with TypeScript project references

With `composite` + declaration emit, `tsc -b` can demand a return-type annotation for portability (TS2742 "cannot be named", TS2883 non-portable inferred type) on the same functions `no-inferrable-return-type` forbids annotating. Resolve it without re-adding the return type:

- annotate the returned _value_ with `satisfies T` in the body — the rule only inspects the return-type slot;
- route the value through a typed identity parameter (`const asT = (x: T) => x; return asT(value);`) — parameters carry portable types where a `const` binding gets narrowed;
- `export` the offending type so the inferred type can be named.

`--fix` strips the annotation and reintroduces the `tsc` error; use one of the above instead of re-annotating.

### zod at the boundary

`consistent-type-assertions: 'never'` plus `no-zod-custom` and `no-type-predicate` steer every deserialization boundary (`JSON.parse`, `event.data`, JSONL) toward a zod schema that _returns_ the typed value rather than `parse(x) as T`. Annotate hand-written schemas as `z.ZodType<T>` to keep their declared type. Blind spot: that annotation only rejects schemas producing values _outside_ `T` — a schema _missing_ a union member still type-checks (the narrower output is assignable to the wider `T`), so a discriminated union can silently drop a case. Keep wire schemas exhaustive by hand.

## Develop

```sh
just install
just check
```

Individual recipes: `just lint`, `just typecheck`, `just test`, `just format`, `just knip`.

## Publish

```sh
just publish
```
