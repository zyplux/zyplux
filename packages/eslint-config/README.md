# @zyplux/eslint-config

Shared ESLint flat config and custom rules. Ships TypeScript source.

## Install

```sh
pnpm add -D @zyplux/eslint-config eslint typescript
```

## Use

`eslint.config.ts`:

```ts
import { zyplux } from '@zyplux/eslint-config';

export default zyplux({ tsconfigRootDir: import.meta.dirname });
```

One call is the whole config: ESLint recommended, type-checked typescript-eslint, unicorn, perfectionist (natural sorting), the custom `@zyplux` rules, vitest (recommended, on `*.{test,spec}.{ts,tsx}`), and prettier last. React is off until you ask for it.

## React renderers

`react` takes a renderer → globs map. Only listed globs receive React rules, so non-React packages match nothing.

```ts
export default zyplux({
  react: {
    dom: ['apps/web/**/*.{ts,tsx}'], // React + DOM rules
    opentui: ['apps/tui/**/*.{ts,tsx}'], // non-DOM renderer
  },
  reactVersion: '19.0',
  tsconfigRootDir: import.meta.dirname,
});
```

- `dom` — `@eslint-react/eslint-plugin` `strict-typescript`, including strict React, JSX, Hooks, DOM, Web API, and naming rules.
- `opentui` / `ink` / `r3f` / `react-pdf` — the same React rules with the DOM preset disabled, since `tsc` validates each renderer's host props through `JSX.IntrinsicElements`.
- Shorthand: `react: true` ≡ `{ dom: ['**/src/**/*.{ts,tsx}'] }`.

## Monorepos

One `zyplux()` call with a renderer map covers a whole repo: set `tsconfigRootDir` once and `projectService` resolves each package's nearest `tsconfig.json`. When packages need genuinely different baselines, scope whole presets with `defineConfig` and share options through `withDefaults`:

```ts
import { defineConfig } from 'eslint/config';
import { zyplux } from '@zyplux/eslint-config';

const tv = zyplux.withDefaults({ tsconfigRootDir: import.meta.dirname });

export default defineConfig(
  { files: ['packages/api/**'], extends: [tv()] },
  { files: ['packages/web/**'], extends: [tv({ react: true })] },
);
```

## Options

| Option            | Default         | Description                                                             |
| ----------------- | --------------- | ----------------------------------------------------------------------- |
| `react`           | `false`         | `true`, or a renderer → globs map (see above)                           |
| `tanstack`        | `false`         | Enforce kebab-case filenames under `routes/`                            |
| `tsconfigRootDir` | `process.cwd()` | Root for typed linting (`projectService`); pin to `import.meta.dirname` |
| `reactVersion`    | `'detect'`      | React version; pin (e.g. `'19.0'`) where workspace detection fails      |
| `ignores`         | `[]`            | Extra ignore globs appended to the defaults                             |

Deprecated, mapped onto `react` for back-compat: `reactFiles` → `react: { dom }`, `nonDomReactFiles` → `react: { opentui }`.

## What's always on

Rule implementations live in `src/rules/`; shared analysis and reporting live in `src/rule-support/`.

- Contract modules and their child modules export schemas, schema collections, and types. Schema detection is shared with naming and nesting checks.
- Public library root barrels contain re-exports. Constants export immutable primitives; type and interface modules contain type-level statements.
- `use-package-type-exports` requires cross-package type imports and re-exports to use the provider's public `package.json` exports. Imports within a package remain unrestricted by this rule.
- `no-type-only-dependencies` rejects dependencies on workspace implementation packages solely for types. Public `/contracts` and `/interfaces` entries are allowed; other public API types require a value import or re-export from the provider somewhere in the consumer package's TypeScript program.
- `test-seam-only-imports` covers every `.test.ts` and `.test.tsx`, including tests outside story directories. Value imports are Vitest API bindings; type-only imports from the same suite API may describe fixtures. Executable helpers reach tests through fixture context. `testApis` maps suite globs to explicit API paths for colocated UI rigs.
- Other custom rules enforce validated JSON, arrow functions, type declarations, clear parameter shapes, and nesting limits.
- Type-checked TypeScript (the full `typescript-eslint` `all` preset), arrow-only functions, `type` over `interface` (except declaration-merging interfaces inside `declare module`/`declare global` blocks), no type assertions.
- No parent-relative (`../`) imports — route through a tsconfig `paths` alias (`@/foo`).
- unicorn + perfectionist (natural sorting); prettier last, so formatting rules are off.
- Your `.gitignore` is honored — patterns from `<tsconfigRootDir>/.gitignore` become ESLint ignores (flat config doesn't read `.gitignore` on its own).

## zod at the boundary

`consistent-type-assertions: 'never'` plus `no-zod-custom`, `no-type-predicate`, and `no-unvalidated-json` steer every deserialization boundary (`JSON.parse`, `await response.json()`, `event.data`, JSONL) toward a zod schema that _returns_ the typed value rather than `parse(x) as T`. `no-unvalidated-json` is the direct enforcer: a `JSON.parse(…)` (matched syntactically) or a `.json()` returning `any`/`Promise<any>` (matched by type, so a typed domain `.json()` is exempt) must flow into a schema `.parse()`/`.safeParse()`. Annotate hand-written schemas as `z.ZodType<T>` to keep their declared type. Blind spot: that annotation only rejects schemas producing values _outside_ `T` — a schema _missing_ a union member still type-checks (a narrower output is assignable to the wider `T`), so a discriminated union can silently drop a case. Keep wire schemas exhaustive by hand.

## Tweaking rules

Flat config is last-wins — append an override after the preset:

```ts
export default [...zyplux({ tsconfigRootDir: import.meta.dirname }), { rules: { 'unicorn/no-null': 'off' } }];
```

Schema detection is shared by contract boundaries, naming, and nesting checks. Nonempty plain objects containing only schemas (including nested collections) count as schemas. Mixed objects, empty objects, arrays, classes, callable objects, optional fields, and open dictionaries do not.

## Test APIs

Select a UI suite's test API relative to `tsconfigRootDir`:

```ts
export default zyplux({
  testApis: { 'apps/web/tests/stories/**/*.test.tsx': 'apps/web/tests/web-rigs.ts' },
  tsconfigRootDir: import.meta.dirname,
});
```
