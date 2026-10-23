# Airlock release surface discovery

Status: deferred. Release targets continue to declare manual `surface` paths in `airlock-targets.toml`.

## Goal

Discover the repository inputs that affect a release, leaving maintainers to declare entry points and additional inputs that the build tools cannot discover. Cover all supported release kinds: npm packages, PyPI distributions, GHCR images and GitHub Actions. A registry identifies where an artifact is published; its language, build and packaging tools determine its inputs.

Prefer existing build metadata and native dependency queries over another import parser or build system. Airlock owns release policy and combines discovered inputs with explicit paths; the existing build tools own resolution and packaging.

## Existing foundations

- [Airlock surface validation](../../apps/airlock/src/release-surface.ts) compares Git changes against declared paths. It does not discover dependencies.
- Airlock's npm publisher inspects the actual packed manifest after lifecycle scripts and packing hooks. This distinguishes bundled implementation packages from dependencies that consumers install separately.
- In `zyp-vps`, `packages/config-validator/build.ts` already obtains esbuild metadata from the validator's two entry points and checks contributing source files against its manual surface. That metadata could supply the discovered source paths instead.
- The core image's `apps/zyp-loop/Dockerfile` uses `turbo prune` to select its workspace dependencies. Its final image contains the pruned workspace, so tracing only runtime imports would describe a different boundary.
- `zyp-vps/scripts/build-dep-graph.ts` and `build-module-graph.ts` generate diagrams with simplified import parsing. They are visualization helpers, not complete release-input resolvers.

## Candidates and tradeoffs

| Tool | Useful capability | Limit |
| --- | --- | --- |
| [pnpm filtering](https://pnpm.io/filtering) and [listing](https://pnpm.io/cli/list) | Native transitive workspace dependency selection, including production-only selection and JSON output | Package granularity; cannot distinguish a shared schema from unrelated runtime code in the same package |
| [esbuild metadata](https://esbuild.github.io/api/#metafile) | Resolved input files and their contribution to the actual bundle | Does not describe all build scripts, copied assets or separately emitted type declarations |
| [Turbo pruning](https://turborepo.dev/docs/reference/prune) | Required internal packages and a pruned lockfile; already used by the core image | Package selection rather than a complete file-level source trace |
| [Knip](https://knip.dev/reference/faq) | Broad source graph, entry discovery and configuration awareness | Documented reporters focus on findings; avoid coupling release correctness to internal graph APIs |
| [Node File Trace](https://github.com/vercel/nft) | Runtime file and asset tracing from entry points without bundling | Another resolver and dependency; TypeScript transformation requires integration |
| [Nx inputs](https://nx.dev/docs/reference/inputs) | Established model combining dependency graphs with explicit build inputs | Adopting a task system solely for release surfaces adds substantial maintenance |

The preferred direction is reuse of native metadata with a small explicit remainder. Do not introduce a general plugin framework or adopt Nx solely for this feature.

## Coverage by release kind

| Kind | Discovery direction | Inputs requiring attention |
| --- | --- | --- |
| npm | Use the actual package build and packed contents. Reuse bundler metadata when available; include source inputs for emitted declarations when the package ships types. | Packing hooks, build configuration, package metadata, copied assets and generators. Follow embedded workspace source; separately published dependencies retain their own release boundary. |
| PyPI | Use the configured build backend's inclusion rules and source-distribution inventory, with wheel contents as an output check. `uv build` invokes the backend; it does not determine included files itself. | `pyproject.toml`, in-tree backend code, shared Python sources copied into the distribution, package data, templates, generators and native extension sources. A wheel alone cannot identify every source used to produce compiled or generated files. |
| GHCR | Use the declared Dockerfile and build context, plus the actual workspace pruning or packaging step. For the current core, native workspace dependency discovery is a candidate to replace the broad `packages` watch. | Ignore files, copied assets, build scripts, package-manager hooks and dependency inputs. A Dockerfile can run arbitrary commands; do not promise complete discovery by parsing `COPY` instructions. |
| GitHub Actions | Start from `action.yml` or `action.yaml`. Follow local action references, JavaScript entry files and their build metadata, or the Dockerfile for a container action. | Shell scripts, templates and files referenced through expressions or computed paths. A remotely versioned action dependency does not make its upstream source part of this repository's surface. |

For Python, [uv's build documentation](https://docs.astral.sh/uv/concepts/projects/build/) describes frontend/backend ownership and the default source-distribution-to-wheel build. The [sdist specification](https://packaging.python.org/en/latest/specifications/source-distribution-format/) defines the source archive, while the backend controls additional contents. Backend-specific support must state its limits; importing Python modules alone is insufficient to discover a distribution's files.

## Correctness and ownership

- Retain manual surfaces as an explicit supported choice. A discovery failure must report a clear error rather than silently omit inputs.
- Generate discovery results during validation using the target's actual build configuration. Avoid committed generated inventories, stale metadata and duplicate entry-point declarations.
- Include declared version sources, relevant package manifests and build configuration. Manifests can change resolution, exports, side effects and dependencies without changing imports.
- Cover additions, removals and renames, including changes to the dependency graph itself. Decide how comparison against the released revision works before defining the configuration contract.
- Preserve architecture boundaries separately from release coverage. The validator's current surface also prevents accidental bundling of runtime implementations; automatic discovery must not turn that into unconditional acceptance of new imports.
- Keep dependency selection native. Whole workspace lockfiles are conservative and can require extra releases for unrelated updates; avoiding that requires relevant dependency comparisons, not a new hand-maintained lockfile parser.
- Surface discovery determines which targets need reviewed release changes. It does not choose semantic version increments, publish artifacts or deploy applications.

## Suggested implementation sequence

1. Define the common input contract and expected behavior across npm, PyPI, GHCR and Actions before choosing TOML syntax. Include representative Python distributions and composite actions in the design.
2. Prove the contract with existing metadata: the validator's esbuild build, one Python build backend, the core's pruned workspace and a composite action. Measure validation cost and unnecessary release bumps.
3. Add only the discovery integrations those examples require, retaining explicit additional paths and manual surfaces. Remove duplicate source lists and parsing logic as each target adopts discovery.
4. Verify shared-source changes, packaging hooks, copied assets, type declarations, generated or compiled outputs, deleted inputs and unrelated changes. Migrate targets incrementally after review.

The immediate priority is reliable manual surfaces. Automatic discovery remains a separate feature; container publication and consumer migration do not depend on it.
