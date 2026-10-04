# 14. [Publishing installable npm packages](14-published-packages.test.ts)

## 14.1 packing release targets

### 14.1.1 ships one manifest with resolvable targets in every npm package

An emitted nested manifest can shadow the publish-time exports and imports in the root manifest, so every npm release package contains only its root `package.json`. Every local path declared by `bin`, `exports`, or `imports` names a packed file. The workspace tests dogfood the ESLint config and `cz` through their public imports.

### 14.1.2 supports Spectra tools through published imports

The packed Spectra package runs a small Vitest test using its public fixtures, matchers, polling, and reporter imports. The temporary consumer reuses the declared Vitest peer from the local installation.

### 14.1.3 supports util imports with an optional TypeScript peer

The packed util package's public root import works without TypeScript installed. Compiler helpers work through their public imports once the optional TypeScript peer is available. The temporary consumer reuses locally installed dependencies; this checks packaged code and exports rather than dependency installation.

## 14.2 selecting a module system

### 14.2.1 keeps module policy in environment presets

The abstract base config owns shared strictness and emit settings without selecting a module system. Each runtime preset owns its resolution contract: Node uses NodeNext, while Bun, Cloudflare Worker, terminal UI, and React web projects preserve modules for their bundler.

## 14.3 selecting emitted artifacts

### 14.3.1 emits declarations for monorepo references and JavaScript only for publishing

Normal presets emit declaration maps to `.tsbuild/` for project references. The explicit `node-pub.json` preset emits installable JavaScript and declarations to `dist/` without maps to unpacked source files.
