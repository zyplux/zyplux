# 14. [Compiler presets](14-compiler-presets.test.ts)

## 14.2 selecting a module system

### 14.2.1 keeps module policy in environment presets

The abstract base config owns shared strictness and emit settings without selecting a module system. Each runtime preset owns its resolution contract: Node uses NodeNext, while Bun, Cloudflare Worker, terminal UI, and React web projects preserve modules for their bundler.

## 14.3 selecting emitted artifacts

### 14.3.1 emits declarations for monorepo references and JavaScript only for publishing

Normal presets emit declaration maps to `.tsbuild/` for project references. The explicit `node-pub.json` preset emits installable JavaScript and declarations to `dist/` without maps to unpacked source files.
