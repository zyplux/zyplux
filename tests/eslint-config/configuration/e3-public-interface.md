# e3. [Configuring eslint through the public zyplux entry point](e3-public-interface.test.ts)

## e3.1 assembling the base flat config

### e3.1.1 enables every rule the zyplux plugin exports

### e3.1.2 scopes vitest rules to test files

### e3.1.3 enables Zod checks in .%s modules

## e3.2 opting into react support

### e3.2.1 leaves react disabled by default

### e3.2.2 scopes the dom renderer to the default src glob once react is enabled

### e3.2.3 defaults the react version to detect and forwards a pinned version through

### e3.2.4 turns off the no-unknown-property rule for non-dom files only once react is enabled

## e3.3 gating the tanstack route rule

### e3.3.1 gates the tanstack route rule behind the tanstack option

## e3.4 scoping react across multiple renderers

### e3.4.1 scopes each renderer in a renderer map to its own file glob

### e3.4.2 keeps the no-unknown-property rule for the dom renderer while turning it off for non-dom renderers

### e3.4.3 enables react and disables no-unknown-property for a renderer map with no dom entry

### e3.4.4 treats an empty renderer map or a renderer with no globs as no react

## e3.5 sharing defaults across zyplux calls

### e3.5.1 applies shared defaults to every call

### e3.5.2 lets a per-call option override a shared default

## e3.6 forwarding caller options into the assembled config

### e3.6.1 appends caller ignores to the default global ignores

### e3.6.2 forwards the tsconfig root dir to the typescript parser options
