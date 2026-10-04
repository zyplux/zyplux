# 14. [Publishing installable npm packages](14-published-packages.test.ts)

## 14.1 packing release targets

### 14.1.1 passes Publint for every built npm archive

Every npm target in `release-targets.toml` is built and packed with pnpm. Each package's `prepack` script runs Publint over the publishable archive with pnpm's manifest transformations applied. Warnings and errors prevent packing.

### 14.1.2 supports util imports with an optional TypeScript peer

The packed util package's root import works without TypeScript installed. Compiler helper imports work once the optional TypeScript peer is available. The temporary consumer reuses locally installed runtime dependencies.

## 14.2 selecting a module system

### 14.2.1 keeps module policy in environment presets

The abstract base config owns shared strictness and emit settings without selecting a module system. Each runtime preset owns its resolution contract: Node uses NodeNext, while Bun, Cloudflare Worker, terminal UI, and React web projects preserve modules for their bundler.

## 14.3 selecting emitted artifacts

### 14.3.1 emits declarations for monorepo references and JavaScript only for publishing

Normal presets emit declaration maps to `.tsbuild/` for project references. The explicit `node-pub.json` preset emits installable JavaScript and declarations to `dist/` without maps to unpacked source files.
