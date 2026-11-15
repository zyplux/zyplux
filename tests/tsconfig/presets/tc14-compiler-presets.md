# tc14. [Compiler presets](tc14-compiler-presets.test.ts)

## tc14.2 selecting a module system

### tc14.2.1 keeps module policy in environment presets

The abstract base config owns shared strictness and emit settings without selecting a module system. Each runtime preset owns its resolution contract: Node uses NodeNext, while Bun, Cloudflare Worker, terminal UI, and React web projects preserve modules for their bundler.

## tc14.3 selecting emitted artifacts

### tc14.3.1 emits declarations for monorepo references and JavaScript only for publishing

Normal presets emit declaration maps to `.tsbuild/` for project references. The explicit `node-pub.json` preset emits installable JavaScript and declarations to `dist/` without maps to unpacked source files.
