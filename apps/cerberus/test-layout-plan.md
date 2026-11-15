# Agreed constraints

- Story documentation and tests may live directly in suite or domain folders without a required `stories/` directory.
- Use repo-wide test file IDs with optional one- or two-letter suite codes, `_test.py` for Python and `.test.ts` for TypeScript.
- Use the file ID in each test case. A story marker distinguishes documented stories from ordinary tests.
- Preserve criterion agreement, package ownership and public-seam enforcement; moving or deleting one side of a pair must not silently remove coverage from these checks.
- Keep the zyp-vps migration on a separate branch from `main` and publish it as a draft once Zyplux PR #71 passes its gates.

## Tasks

- [x] Define one path-independent discovery contract for Python and TypeScript story pairs, evaluating existing criterion IDs and document links before adding metadata; detect orphaned and ambiguous pairs independently of successful matching.
- [x] Use the same discovered Python story files for lockstep and CLI/library seam checks; preserve ownership boundaries and directory-local criterion namespaces.
- [x] Cover flattened suites containing story tests, component tests and unrelated Markdown, including missing partners, duplicate IDs, stale links, malformed stories and cross-package mismatches. Preserve each language's existing criterion/title semantics explicitly.
- [x] Audit TypeScript ESLint story selection and suite API resolution, including the `stories/`-dependent `#fixtures` rule, so flattening cannot relax public-seam checks.
- [x] Enforce file IDs across executable tests and require case IDs to use their file's ID. Rename the Zyplux tests and update story links and criteria.
- [x] Dogfood discovery and the flattened layout in zyplux, update Cerberus documentation and run applicable lint, typechecking and focused regression tests before release.
- [ ] Apply the same test layout and ID rules in the isolated zyp-vps worktree, validate it with local Cerberus, and open a draft PR.
