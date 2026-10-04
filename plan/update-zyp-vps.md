# Update zyp-vps

Prerequisite: publish the prepared Zyplux package releases.

## Shared packages and testing

- [ ] Upgrade `@zyplux/cz`, `@zyplux/eslint-config`, and `zyplux-cerberus`; add published `@zyplux/spectra` and `@zyplux/util`.
- [ ] Replace the local Spectra workspace with the published package; remove its implementation, framework tests, and obsolete workspace/project configuration.
- [ ] Update consumer dependency declarations, TypeScript references, Vitest/Knip project inventories, and lockfiles for the installed packages.
- [ ] Adopt shared fixtures, fakes, matchers, and test polling where applicable; retain application-specific rigs and helpers locally.
- [ ] Use the shared `JournaldReporter` in root and E2E Vitest configurations, preserving their journal identifiers and reporting behavior.
- [ ] Replace `@zyplux/spectra/lap-timer` with `@zyplux/util/lap-timer`; move any retained module-reference and type-dependency consumers to Util.
- [ ] Replace `@zyplux/spectra/matchers/element-collections` with `@zyplux/spectra/test-matchers`; use supported subpaths for any other affected Util or programmatic cz imports.
- [ ] Verify test API composition, matcher registration, and journal identifiers across smoke, E2E, and colocated UI suites.

Keep TypeScript and Python suite execution sequential. Python journaling and unified filtered execution remain deferred; no new test launcher is required.

## Shared architecture checks

- [ ] Declare the application scope, its `@zyplux/domain-model` contract keeper, and allowed dependency directions, including the widget/workflow-engine boundary.
- [ ] Adopt shared ESLint checks for barrels, primitive constants, schemas, type-only modules, type ownership, and declared dependency direction.
- [ ] Enable test seam enforcement for every story suite, including the dashboard and widget rig APIs.
- [ ] Replace broad schema-boundary and nesting overrides with the shared schema detection and exact Zod nesting exemption.
- [ ] Review matcher `this` and context-bound `expect` exceptions; retain only necessary, narrowly scoped exceptions for supported Vitest APIs.
- [ ] Enable Cerberus package exports, side effects, scoped keepers, dependency direction, project references, and Worker runtime checks.
- [ ] Remove retired `cli_ts_test_seam`, `lib_ts_test_seam`, and `fixture_roles_ts` overrides; enable the current story, Vitest runner, and coverage checks.
- [ ] Remove the replaced `smb1` architecture assertions, `smb2` test-import guard, and unused scanners after their shared replacements pass.
- [ ] Preserve product-specific smoke assertions and production bundle validation for third-party dependencies and framework entry points.

## Known repository gaps

- [ ] Align the `doubles` `/interfaces` export with its source module name.
- [ ] Complete missing story documents and acceptance criteria across smoke and colocated UI suites.
- [ ] Resolve duplicate dashboard `9.1` IDs in configuration reload and Teams user picker stories.
- [ ] Add missing API Teams recipient criterion `5.1` and workflow resilience criterion `7.4`.
- [ ] Refresh generated story links.
- [ ] Configure root Vitest coverage thresholds to the shared floor and ensure coverage is fresh before Cerberus runs.
- [ ] Resolve the missing justfile module include.

## Remaining quality checks and cleanup

- [ ] Reassess the `workflow_toolchain_only` suppression against the current checker and remove it once verified.
- [ ] Run the current `jscpd` check, fix duplication findings, and remove its obsolete suppression.
- [ ] Run Fallow with fresh coverage, fix findings, and re-enable it.
- [ ] Adopt shared support for equivalent CI commands, separate Knip policies, and recipe behavior before removing the corresponding suppressions.
- [ ] Review all remaining Cerberus and ESLint overrides; fix findings and remove stale explanations and exceptions.
- [ ] Update repository documentation and run the full quality gate, existing smoke/E2E suites, UI tests, and production bundle checks before completing adoption.
