# 3. [Configuring eslint through the public zyplux entry point](3_public-interface.test.ts)

## 3.1 assembling the base flat config

### 3.1.1 produces a non-empty flat config array

### 3.1.2 enables every rule the zyplux plugin exports

### 3.1.3 scopes vitest rules to test files

## 3.2 opting into react support

### 3.2.1 leaves react disabled by default

### 3.2.2 scopes the dom renderer to the default src glob once react is enabled

### 3.2.3 defaults the react version to detect and forwards a pinned version through

### 3.2.4 turns off the no-unknown-property rule for non-dom files only once react is enabled

## 3.3 gating the tanstack route rule

### 3.3.1 gates the tanstack route rule behind the tanstack option

## 3.4 scoping react across multiple renderers

### 3.4.1 scopes each renderer in a renderer map to its own file glob

### 3.4.2 keeps the no-unknown-property rule for the dom renderer while turning it off for non-dom renderers

### 3.4.3 enables react and disables no-unknown-property for a renderer map with no dom entry

### 3.4.4 treats an empty renderer map as no react

## 3.5 sharing defaults across zyplux calls

### 3.5.1 applies shared defaults to every call

### 3.5.2 lets a per-call option override a shared default
