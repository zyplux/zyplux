# @zyplux/eslint-config

Shared ESLint flat config and custom rules. Ships TypeScript source — consumed directly under Bun.

## Install

```sh
bun add -D @zyplux/eslint-config eslint typescript
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
    dom: ['apps/web/**/*.{ts,tsx}'], // full eslint-plugin-react (DOM)
    opentui: ['apps/tui/**/*.{ts,tsx}'], // non-DOM renderer
  },
  reactVersion: '19.0',
  tsconfigRootDir: import.meta.dirname,
});
```

- `dom` — DOM rules on (eslint-plugin-react `recommended` + `jsx-runtime` + React Hooks).
- `opentui` / `ink` / `r3f` / `react-pdf` — same, but `react/no-unknown-property` off, since `tsc` already validates each renderer's host props through `JSX.IntrinsicElements`.
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

- Custom `@zyplux` rules: `contracts-only-schemas` (on `**/src/contracts.ts` only), `no-anonymous-param-type`, `no-identity-cast`, `no-return-array-push`, `no-schemas-outside-contracts` (on `**/src/**` except the contracts module), `no-stray-pascal-const`, `no-type-annotations`, `no-type-predicate`, `no-unvalidated-json`, `no-zod-custom`, `prefer-arrow-functions`, `prefer-destructured-params`.
- Type-checked TypeScript (the full `typescript-eslint` `all` preset), arrow-only functions, `type` over `interface`, no type assertions.
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
