# 15. [Upgrading the repository toolchain and dependencies](15-upgrade.test.ts)

## 15.1 upgrading a mixed workspace

### 15.1.1 uses the newest same-major Node release with a real Docker registry manifest

`cz upgrade` keeps pnpm and Node within their declared majors, accepts a Node image only when Docker's authenticated registry returns its content digest, synchronizes Dockerfile mirrors, upgrades JavaScript dependencies, and then upgrades an existing Python workspace.

### 15.1.2 uses pnpm selection in interactive mode and leaves declined toolchain pins alone

`cz upgrade --interactive` asks before changing Node and external toolchain pins, delegates dependency selection to pnpm, and skips Python commands when no Python workspace exists.

### 15.1.3 supports a JavaScript-only workspace without an external tool pin

The external tool pin and Python workspace are optional; dependency and pnpm upgrades still run when Node is current.
