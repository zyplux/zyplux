# Plan: replace Bun with Node 26 + pnpm

**Status: inventory only, nothing actioned yet.** Every change needed to move this repo off Bun onto Node 26 (runtime) and pnpm (package manager, chosen over npm because npm has no `catalog:` protocol). Check items off as they're resolved.

Node 26 refuses to type-strip files under `node_modules`, so the published packages must ship compiled JS. That is the one irreversible consequence of this migration and it drives items 32–46.

`zyp-vps` already runs Node 26.5 + pnpm 11 with nine cerberus bites switched off in its `cerberus.toml`; items 90–118 are what let it switch them back on.

## 1 Runtime APIs

1. [ ] `packages/util-ts/src/shell.ts` — replace all ~40 `Bun.$` call sites with a `node:child_process` harness.
2. [ ] `packages/util-ts/src/shell.ts` — reimplement `.quiet()`, `.nothrow()`, `.cwd()`, `.env()`, `.text()` chaining on the new harness.
3. [ ] `packages/util-ts/src/shell.ts` — reimplement the tagged-template argument escaping `Bun.$` provides.
4. [ ] `packages/util-ts/src/shell.ts:105` — `$`'s direct-call passthrough currently types off `Parameters<typeof Bun.$>`; retype against the new harness.
5. [ ] `packages/util-ts/src/shell.ts:108` — `captureMerged` relies on `2>&1` inside the template; needs explicit shell or stream-merging.
6. [ ] `packages/util-ts/src/shell.ts` — extract the exec primitive into its own module so tests can `vi.mock` it instead of reassigning a global.
7. [ ] `packages/util-ts/src/json.ts:11` — `Bun.file(path).json()` → `node:fs/promises` read + parse.
8. [ ] `packages/util-ts/src/poll.ts:9` — `Bun.sleep` → `node:timers/promises`.
9. [ ] `packages/util-ts/src/toml.ts:5` — `Bun.TOML.parse` → `smol-toml` (Node has no TOML parser).
10. [ ] Add `smol-toml` to the catalog and to `packages/util-ts` dependencies; decide dependency vs peer, since `@zyplux/util` is published.
11. [ ] Confirm `smol-toml` preserves the syntax-error/schema-error distinction locked in by `tests/util-ts/stories/4-toml.test.ts`.
12. [ ] `apps/cz/src/deps-catalog.ts:30` — `Bun.file(file).text()` → `node:fs/promises`.
13. [ ] `apps/cz/src/commands/deps-catalog.ts:38` — `Bun.write` → `node:fs/promises`.
14. [ ] `apps/cz/src/commands/publish-tagged-target.ts:24` — `bun pm pack && bunx npm@11 publish` → `pnpm pack && npm publish`.
15. [ ] `apps/cz/src/index.ts:1` — `#!/usr/bin/env bun` → `node`.

## 2 Module resolution and TypeScript config

16. [ ] Add explicit `.ts` extensions to 112 extensionless relative imports across `apps/cz/src`, `packages/*/src`, `packages/eslint-config/scripts`, `tests/*/src`, `tests/*/fixtures`, `tests/*/stories`.
17. [ ] `packages/tsconfig/base.json` — `moduleResolution: "bundler"` → `"nodenext"`.
18. [ ] `packages/tsconfig/base.json` — `module: "Preserve"` → `"nodenext"`.
19. [ ] `packages/tsconfig/base.json` — add `allowImportingTsExtensions`.
20. [ ] `packages/tsconfig/base.json` — add `rewriteRelativeImportExtensions` (needed once packages emit JS).
21. [ ] `packages/tsconfig/base.json` — `emitDeclarationOnly: true` → full emit for published packages.
22. [ ] `packages/tsconfig/base.json` — keep `erasableSyntaxOnly: true`; it is already what makes the source Node-strippable.
23. [ ] `packages/tsconfig/bun.json` — replace with a `node.json` preset carrying `types: ["node"]`.
24. [ ] `packages/tsconfig/bun.json` — decide whether to keep it as a deprecated alias; five sibling repos extend it, so removal is a breaking change.
25. [ ] `packages/tsconfig/tui.json:7` — `types: ["bun", "react"]` → `["node", "react"]`.
26. [ ] `packages/tsconfig/web.json:8` — `types: ["bun", "react", "react-dom"]` → `["node", ...]`.
27. [ ] `packages/tsconfig/package.json` — `files` list and version bump for the preset rename.
28. [ ] `tsconfig.tooling.json:2` — extends `@zyplux/tsconfig/bun.json`.
29. [ ] `packages/util-ts/tsconfig.json:2` — extends `@zyplux/tsconfig/bun.json`.
30. [ ] `packages/eslint-config/tsconfig.json:2` — extends `@zyplux/tsconfig/bun.json`.
31. [ ] `apps/cz/tsconfig.json` and `tests/*/tsconfig.json` — same preset swap.

## 3 Publishing (packages must ship compiled JS)

32. [ ] Add a build step producing `.js` + `.d.ts` for `packages/util-ts`.
33. [ ] Add a build step for `packages/eslint-config`.
34. [ ] Add a build step for `apps/cz`.
35. [ ] Add a build step for `packages/spectra` (`@zyplux/spectra` is a published release target).
36. [ ] `packages/util-ts/package.json` — `exports` from `./src/*.ts` to built output.
37. [ ] `packages/eslint-config/package.json` — `exports` from `./src/*.ts` to built output.
38. [ ] `apps/cz/package.json` — `exports` and `bin` from `./src/index.ts` to built output.
39. [ ] `packages/spectra/package.json` — `exports` from `./src/index.ts` to built output.
40. [ ] All four — `files` must include the build output, not (only) `src`.
41. [ ] All four — verify the `#`-subpath `imports` maps still resolve post-build.
42. [ ] Add `prepack` (or equivalent) so packing cannot publish stale output.
43. [ ] `release-targets.toml` — `surface` globs for the four packages must cover build inputs, not output.
44. [ ] Verify `pnpm pack` tarball contents for each package before the first real publish.
45. [ ] Version-bump all four packages; the published shape changes even where the API does not.
46. [ ] Decide whether `@zyplux/tsconfig` needs a bump (JSON-only, but the preset set changes).

## 4 Package manager and lockfile

47. [ ] Delete `bun.lock`, generate `pnpm-lock.yaml`.
48. [ ] Create `pnpm-workspace.yaml`; move the `packages/*`, `apps/*`, `tests/*` globs out of `package.json`.
49. [ ] Move the 24-entry `catalog` out of `package.json` into `pnpm-workspace.yaml`.
50. [ ] Verify every `catalog:` and `workspace:*` specifier still resolves under pnpm.
51. [ ] `package.json` — `engines.bun` → `engines.node` (`>=26`).
52. [ ] `package.json` — `packageManager: "bun@1.3.14"` → pnpm.
53. [ ] Add an explicit pnpm bootstrap step; Corepack is no longer distributed with Node as of v25.
54. [ ] Add `.nvmrc` (or `.node-version`) pinning the Node version.
55. [ ] Add `.npmrc` if pnpm hoisting/linking defaults need adjusting for this workspace.
56. [ ] Drop `@types/bun` from the catalog; add `@types/node`.
57. [ ] Drop `@types/bun` from all 8 manifests that declare it: root, `apps/cz`, `packages/util-ts`, `packages/eslint-config`, `tests/cz`, `tests/eslint-config`, `packages/spectra`, `tests/util-ts`.
58. [ ] Verify `npm-check-updates` still drives upgrades correctly against a pnpm catalog.

## 5 Scripts and justfile

59. [ ] `package.json:46` — `lint:fix` invokes `bun run lint`.
60. [ ] `package.json:49` — `cz` script invokes `bun apps/cz/src/index.ts`.
61. [ ] `packages/eslint-config/package.json:49` — `dump-rules` invokes `bun run scripts/dump-rules.ts`.
62. [ ] `justfile:21` — `bun install`.
63. [ ] `justfile:26,27` — `bun run knip` (both passes).
64. [ ] `justfile:32` — `bun run typecheck`.
65. [ ] `justfile:37,38` — `bun run lint:fix`, `bun run format`.
66. [ ] `justfile:57,64,65` — upgrade recipes.
67. [ ] `justfile:72` — `bun run cz push-branch`.
68. [ ] `justfile:79` — `bun run cz clean`.
69. [ ] `justfile:87` — `bun run cz clone-reference-repo`.
70. [ ] `justfile:91` — `bun run --cwd packages/eslint-config dump-rules`.
71. [ ] `justfile:99` — `bun run --silent cz release-bumped-targets`.
72. [ ] Add a `build` recipe and wire it into `check` ahead of `test`.
73. [ ] Items 62–71 land in the `# BASELINE` region — edit `apps/cerberus/src/cerberus/baseline.just`, never the justfile.

## 6 CI and container image

74. [ ] `containers/ci/Containerfile:1` — `FROM oven/bun:1.3.14-debian` → a Node 26 base.
75. [ ] `containers/ci/Containerfile:4` — image description says "bun + uv + git, no Node".
76. [ ] `containers/ci/Containerfile` — install pnpm in the image.
77. [ ] `containers/ci/Containerfile:5` — bump `org.opencontainers.image.version`; publish a new GHCR tag.
78. [ ] `.github/workflows/ci.yml` — `bun install --frozen-lockfile`.
79. [ ] `.github/workflows/ci.yml` — `bun run knip` / `typecheck` / `lint` / `test` steps.
80. [ ] `.github/workflows/ci.yml` — `bunx prettier --check .`.
81. [ ] `.github/workflows/ci.yml` — pin the new CI image tag.
82. [ ] `.github/workflows/ci.yml` — add a build step before `test`.
83. [ ] `.github/workflows/bootstrap-npm.yml` — `oven-sh/setup-bun` → `actions/setup-node`.
84. [ ] `.github/workflows/bootstrap-npm.yml` — `bun install --frozen-lockfile`, `bun run cz`.
85. [ ] `.github/workflows/release.yml` — `oven-sh/setup-bun` in all four jobs (`resolve`, `npm`, `pypi`, `ghcr`).
86. [ ] `.github/workflows/release.yml` — `bun install --frozen-lockfile` in all four jobs.
87. [ ] `.github/workflows/release.yml` — `bun run cz` invocations in all four jobs.
88. [ ] `.github/workflows/release.yml` — publish jobs must build before packing.
89. [ ] Add pnpm-store caching to CI.

## 7 Cerberus (org gate — must accept both toolchains, not swap to Node-only)

90. [ ] `cerberus.toml` `[ci_check_sequence.required].ts` — the six literal `bun …` commands must become package-manager-aware.
91. [ ] `bites/ci_check_sequence_bite.py:91` — container requirement and its "Node-free guarantee" message.
92. [ ] `cerberus.toml` `[workflow_toolchain_only].allowed_setup_actions` — add `actions/setup-node`.
93. [ ] `bites/workflow_toolchain_only_bite.py:30` — the `pnpm|yarn … global` regex blocks the standard pnpm bootstrap.
94. [ ] `bites/workflow_toolchain_only_bite.py:50` — failure message says "the toolchain is uv + bun".
95. [ ] `workspaces.py:19` — `bun_member_globs` reads `package.json` `workspaces`; under pnpm membership lives in `pnpm-workspace.yaml`.
96. [ ] `workspaces.py` — rename the function once it is no longer Bun-specific.
97. [ ] `bites/zyplux_deps_latest_bite.py:82` — reads `bun.lock`.
98. [ ] `bites/zyplux_deps_latest_bite.py:57` — `_npm_usages` regex parses bun.lock format; pnpm-lock.yaml differs.
99. [ ] `bites/catalog_pinned_deps_bite.py` — reads the catalog from `package.json`.
100. [ ] `bites/story_docs.py:234` — bun workspace member dirs.
101. [ ] `bites/test_seam.py:85` — bun workspace member dirs.
102. [ ] `bites/jscpd_bite.py:47` — `bun_member_globs` call.
103. [ ] `bites/jscpd_bite.py:54` — `bunx` subprocess invocation.
104. [ ] `bites/fallow_bite.py:267` — `bunx` subprocess invocation.
105. [ ] `bites/fallow_bite.py:201,225` — `bunx` rerun hints in failure messages.
106. [ ] `bites/fallow_bite.py:20` — module docstring describes the `bunx` pipe chain.
107. [ ] `bites/justfile_bite.py:36` — `_CZ_CLEAN_INVOCATIONS` accepts only `cz` / `bun run cz` / `bunx cz`.
108. [ ] `bites/justfile_bite.py:91,252` — managed tools must run via `uv run`/`bunx`.
109. [ ] `bites/justfile_bite.py:79` — docstring lists the accepted invocations.
110. [ ] `bites/vitest_bite.py:23,24,41,64,72,82` — the `bun:test` / `bun test` bans go vestigial; keep or generalize deliberately.
111. [ ] `tool_pins.py:1` — docstring says the tools run via `bunx`.
112. [ ] `baseline.just:18,20,25,26,29,31,36,37,45,56,63,64,71,78` — every `bun` invocation.
113. [ ] `baseline.just` — add the `build` recipe from item 72.
114. [ ] `cerberus.toml` `[knip].allowed_customizations` — check whether pnpm changes the required `ignoreBinaries`.
115. [ ] Confirm the `wrapped_tools` list still holds when tools run via `pnpm exec` rather than `bunx`.
116. [ ] Bump `apps/cerberus/pyproject.toml` version and cut a release.
117. [ ] Verify the five Bun sibling repos still pass on the released cerberus before merging.
118. [ ] Re-enable `[ci_check_sequence]` and `[workflow_toolchain_only]` in `zyp-vps/cerberus.toml`.

## 8 Tests and fixtures

119. [ ] `packages/spectra/src/fakes/shell-fake.ts:113,133,134,136` — the fake reassigns `Bun.$`; move to mocking the exec module from item 6.
120. [ ] `packages/spectra/src/fakes/shell-fake.ts:8,9` — `ShellPromise` / `ShellValue` types derive from `Bun.$`.
121. [x] `packages/spectra/src/library-test-api.ts` — sleep fixtures use mocked `node:timers/promises`.
122. [ ] `packages/spectra/package.json` — description and `bun` keyword.
123. [ ] `tests/util-ts/stories/6-shell.test.ts:112` — story name references `Bun.$`.
124. [ ] `tests/cz/stories/5-bootstrap-npm-target.test.ts:32,43,47` — asserts on `bun pm pack` / `bunx npm@11`.
125. [ ] `tests/cz/stories/8-publish-tagged-target.test.ts:20,27,31,32` — same assertions.
126. [ ] `tests/util-ts/stories/1-manifest.test.ts:8` — fixture manifest contains `"build": "bun build"`.
127. [ ] Verify `vitest.config.ts` `isolate: false` still behaves under Node.
128. [ ] Verify istanbul coverage still resolves `src` paths once packages emit to a build directory.

## 9 Docs and comments

129. [ ] `README.md:20` — `@zyplux/util` described as "Bun utilities".
130. [ ] `README.md:29` — "Dual workspace: bun (TS) + uv".
131. [ ] `CLAUDE.md:9` — gate described as spanning "the bun (JS/TS) and uv" workspaces.
132. [ ] `CLAUDE.md:11` — `bun run test` regenerates coverage.
133. [ ] `packages/util-ts/README.md:3` — "Small Bun utilities … consumed directly under Bun".
134. [ ] `packages/util-ts/README.md:8` — `bun add` install line.
135. [ ] `packages/util-ts/README.md:36` — `Bun.file` in the `readJson` description.
136. [ ] `packages/util-ts/README.md:45` — `$` documented as `Bun.$` augmented.
137. [ ] `packages/util-ts/README.md:47` — manifest schema described as reading "bun `workspaces`/`catalog`".
138. [ ] `packages/util-ts/package.json` — description and `bun` keyword.
139. [ ] `packages/eslint-config/README.md:3` — "consumed directly under Bun".
140. [ ] `packages/eslint-config/README.md:8` — `bun add -D` install line.
141. [ ] `packages/tsconfig/README.md:10,17` — `bun.json` preset row and example.
142. [ ] `apps/cz/package.json` — `bun` keyword.
143. [ ] `docs/guide/publish.md:36,39,40` — `bunx npm@11` login/trust instructions.
144. [ ] `.gitignore:1` — "# JavaScript / bun" comment.
145. [ ] `ruff.toml:17` — S607 comment lists `bun` as tooling invoked off PATH.
146. [ ] `packages/eslint-config/src/rules/type-aware/no-unvalidated-json.ts:64` — rule description cites `Bun.file` as a boundary example.
147. [ ] `docs/roadmap/knip-and-export-discipline.md:51,94` — Bun bundler and bundler-mode resolution notes.

## 10 Machine setup (reproducibility)

148. [ ] `apps/totchef/examples/totchef_recipe.toml:160` — `[url.bun]` installs Bun; add a Node install path.
149. [ ] `apps/totchef/examples/totchef_recipe.toml:164` — `[bun]` section installs `@zyplux/cz` globally; needs a pnpm equivalent.
150. [ ] `apps/totchef` — add a node/pnpm cook alongside `bun_cook`.
151. [ ] Out of scope, do not remove: `apps/totchef`'s `[bun]` cook and `skills_cook`'s `bunx` usage are product features configuring user machines, not repo infrastructure.

## 11 Node 26 features worth adopting

152. [ ] Enable the portable compile cache for `cz` to recover part of Bun's startup advantage.
153. [ ] Cache the compile-cache directory in CI.
154. [ ] Consider a cerberus bite asserting CI-invoked tooling runs under Node's permission model (`--permission`, `--allow-*`); Bun has no equivalent.
155. [ ] Not applicable, checked: `Temporal` (no `Date` usage anywhere in `apps/`, `packages/`, `tests/`), `Map.getOrInsertComputed()` (existing `Map`/`Set` usage is membership testing, not memoization), `Iterator.concat()`, `crypto.randomUUIDv7()`, undici 8, `req.signal`.

## 12 Verification

156. [ ] `just c` passes clean.
157. [ ] `bunx`-free: no `bun` or `bunx` string remains outside `apps/totchef` and this document.
158. [ ] Install a packed tarball of each published package into a scratch Node project and run it.
159. [ ] Install the same tarballs into a scratch Bun project; the five Bun sibling repos must keep working.
160. [ ] Full CI run on the new image, including the release workflow via a dry-run tag.
