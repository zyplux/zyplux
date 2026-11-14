# Agreed constraints

- Story documentation and tests may live directly in suite or domain folders without a required `stories/` directory.
- Keep descriptive, unique test basenames while allowing ordinary component tests and unrelated Markdown beside story pairs.
- Preserve criterion agreement, package ownership and public-seam enforcement; moving or deleting one side of a pair must not silently remove coverage from these checks.
- Keep zyp-vps PR #74 independent; migrate its test layout in a separate follow-up after the shared tooling is released.

## Tasks

- [x] Define one path-independent discovery contract for Python and TypeScript story pairs, evaluating existing criterion IDs and document links before adding metadata; detect orphaned and ambiguous pairs independently of successful matching.
- [x] Use the same discovered Python story files for lockstep and CLI/library seam checks; preserve ownership boundaries and directory-local criterion namespaces.
- [x] Cover flattened suites containing story tests, component tests and unrelated Markdown, including missing partners, duplicate IDs, stale links, malformed stories and cross-package mismatches. Preserve each language's existing criterion/title semantics explicitly.
- [x] Audit TypeScript ESLint story selection and suite API resolution, including the `stories/`-dependent `#fixtures` rule, so flattening cannot relax public-seam checks.
- [x] Inventory test basename collisions and establish repository-wide uniqueness for executable test files, without treating shared fixture or configuration filenames as test basenames; rename tests and repair links and discovery configuration together.
- [x] Dogfood discovery and the flattened layout in zyplux, update Cerberus documentation and run applicable lint, typechecking and focused regression tests before release.
- [ ] Release Cerberus and any required ESLint changes before updating consumer locks and flattening their layouts; inventory affected consumers and migrate zyp-vps separately from PR #74. Existing nested suites must remain recognized by the same discovery contract during rollout.
