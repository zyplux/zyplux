# 14. [Publishing installable npm packages](14-published-packages.test.ts)

## 14.1 packing release targets

### 14.1.1 ships one manifest with resolvable targets in every npm package

An emitted nested manifest can shadow the publish-time exports and imports in the root manifest, so every npm release package contains only its root `package.json`. Every local path declared by `bin`, `exports`, or `imports` names a packed file. The workspace tests dogfood the ESLint config and `cz` through their public imports.

### 14.1.2 filters tests from an isolated installation with only runtime dependencies

The packed `cz` command accepts a test filter in a fresh project with no matching tests. Its installation has access to only the runtime dependencies declared in its packed manifest, so workspace development dependencies cannot hide missing imports.

## 14.2 selecting a module system

### 14.2.1 keeps module policy in environment presets

The abstract base config owns shared strictness and emit settings without selecting a module system. Each runtime preset owns its resolution contract: Node uses NodeNext, while Bun, Cloudflare Worker, terminal UI, and React web projects preserve modules for their bundler.

## 14.3 selecting emitted artifacts

### 14.3.1 emits declarations for monorepo references and JavaScript only for publishing

Normal presets emit declaration maps to `.tsbuild/` for project references. The explicit `node-pub.json` preset emits installable JavaScript and declarations to `dist/` without maps to unpacked source files.
