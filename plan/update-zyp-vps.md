# Update zyp-vps

Prerequisite: publish `zyplux-cerberus` 0.21.0, `@zyplux/eslint-config` 0.11.0, `@zyplux/tsconfig` 0.3.2, `@zyplux/util` 0.9.0, and `@zyplux/spectra` 0.3.1 before migration.

## Shared packages and testing

- [ ] Upgrade `@zyplux/cz`, `@zyplux/eslint-config`, and `zyplux-cerberus`; add published `@zyplux/spectra` and `@zyplux/util`.
- [ ] Replace the local Spectra workspace with the published package; remove its implementation, framework tests, obsolete workspace/project configuration, and `systemd-cat` Knip exemptions.
- [ ] Update consumer dependency declarations, TypeScript references, Vitest/Knip project inventories, and lockfiles for the installed packages.
- [ ] Adopt shared fixtures, fakes, matchers, and test polling where applicable; retain application-specific rigs and helpers locally.
- [ ] Use the shared `JournaldReporter` in root and E2E Vitest configurations; align options to preserve `zyp-<project>` and console tags, and update journal commands for unattributed output.
- [ ] Replace `@zyplux/spectra/lap-timer` with `@zyplux/util/lap-timer`; move any retained module-reference and type-dependency consumers to Util.
- [ ] Replace `@zyplux/spectra/matchers/element-collections` with `@zyplux/spectra/test-matchers`; use supported subpaths for any other affected Util or programmatic cz imports.
- [ ] Verify test API composition, matcher registration, and journal identifiers across smoke, E2E, and colocated UI suites.
- [ ] Verify Vitest peer compatibility and retain TypeScript dependencies for any Util compiler helpers still used locally.

Keep TypeScript and Python suite execution sequential. Python journaling and unified filtered execution remain deferred; no new test launcher is required.

## Shared architecture checks

- [ ] Adopt shared ESLint checks for barrels, primitive constants, schemas, type-only modules, public package type exports, and type-only dependencies.
- [ ] Enable test seam enforcement for every story suite, including the dashboard and widget rig APIs.
- [ ] Replace broad schema-boundary and nesting overrides with the shared schema detection and exact Zod nesting exemption.
- [ ] Review matcher `this` and context-bound `expect` exceptions; retain only necessary, narrowly scoped exceptions for supported Vitest APIs.
- [ ] Adopt Cerberus package exports, side effects, project references, and Worker runtime checks; retain the pnpm release-age policy.
- [ ] Remove retired `cli_ts_test_seam`, `lib_ts_test_seam`, and `fixture_roles_ts` overrides; enable the current story and Vitest runner checks.
- [ ] Remove the replaced `smb1` architecture assertions, `smb2` test-import guard, `sdp8` release-age check, and unused scanners after their shared replacements pass.
- [ ] Retain local keeper assertions and dependency restrictions for domain-model, kernel, and the widget/workflow-engine boundary; retain explicit keeper barrel checks where shared ESLint configuration does not select them.
- [ ] Preserve product-specific smoke assertions and production bundle validation for third-party dependencies and framework entry points.
- [ ] Set `[vitest_coverage].off = true` with a comment explaining that container E2E tests do not collect TypeScript source coverage; enable the independent Vitest runner check.

## Known repository gaps

- [ ] Align the `doubles` `/interfaces` export with its source module name.
- [ ] Complete missing story documents and acceptance criteria across smoke and colocated UI suites.
- [ ] Resolve duplicate E2E dashboard section `9` and criterion `9.1` IDs in configuration reload and Teams user picker stories.
- [ ] Add missing API Teams recipient criterion `5.1` and workflow resilience criterion `7.4`.
- [ ] Refresh generated story links.

## Remaining quality checks and cleanup

- [ ] Remove the `workflow_toolchain_only` suppression; the current checker accepts the existing CI toolchain setup.
- [ ] Run the current `jscpd` check, fix duplication findings, and remove its obsolete suppression.
- [ ] Run Fallow against current source, refresh any coverage reports it consumes, fix findings, and re-enable it.
- [ ] Resolve checker compatibility with equivalent CI commands, separate Knip policies, and application-specific justfile recipes before removing their suppressions; preserve zyp-vps's existing sequential CI test commands.
- [ ] Review all remaining Cerberus and ESLint overrides; fix findings and remove stale explanations and exceptions.
- [ ] Update repository documentation and run the full quality gate, existing smoke/E2E suites, UI tests, and production bundle checks before completing adoption.
