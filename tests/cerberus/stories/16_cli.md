# 16. [Linting a repo checkout from the command line](test_16_cli.py)

## 16.1 invoking lint as the default command

### 16.1.1 passes a fully conforming checkout given an explicit path

### 16.1.2 defaults to the current directory when no path argument is given

### 16.1.3 prints one line per active bite with its id and outcome

### 16.1.4 appends a bite's measured detail to its line

## 16.2 surfacing check failures end to end

### 16.2.1 fails when the ci workflow file is missing

### 16.2.2 fails on trailing whitespace in the justfile

## 16.3 fixing what can be fixed automatically

### 16.3.1 strips trailing whitespace in place so the rerun then passes

## 16.4 limiting a run to specific named checks

### 16.4.1 runs only the checks named on the command line

### 16.4.2 rejects an unknown check name given on the command line

## 16.5 pointing the linter at an alternate config file

### 16.5.1 uses the recipe requirements from the given config file instead of the bundled defaults

### 16.5.2 rejects a config file whose section is not a table

## 16.6 switching bites off in configuration

Any bite switches off with `off = true` in its `[<bite id>]` config table — the same table that carries its other settings, handled uniformly by the runner rather than each bite. The bundled defaults ship bites that only one repo can act on (like `tool_pins_latest`) as off, a repo overlay switches any bite off or back on (`off = false`), and an off bite leaves no trace in the output. Naming an off bite explicitly with `--check` still runs it: an explicit ask outranks a default.

### 16.6.1 leaves an off bite out of the run and the output

### 16.6.2 runs an off bite when named explicitly with check

### 16.6.3 re-enables a bundled-off bite when the repo overlay sets off to false

### 16.6.4 warns and carries on when an off table names an unknown bite

## 16.7 listing the available checks

### 16.7.1 lists every registered check by id

## 16.8 printing the installed version

### 16.8.1 prints the cerberus version

## 16.9 guarding the lint command surface against unknown options

### 16.9.1 rejects an option the lint command never defined

## 16.10 isolating a crashing check

### 16.10.1 reports a crashing check as an error instead of aborting the run

## 16.11 rendering a skipped bite distinctly

### 16.11.1 renders a skipped bite with its skip glyph and reason

## 16.12 overriding configuration from a repo-root cerberus.toml

A repo tightens org defaults without forking them: a `cerberus.toml` at the repo root overlays the bundled configuration key by key, so the file only names what it overrides. An explicit `--config` file overlays the same way, standing in for the repo's own file — the bundled defaults always stay the base.

### 16.12.1 overlays a repo root cerberus.toml onto the bundled defaults

### 16.12.2 applies an explicit config file in place of the repo's own overlay

## 16.13 printing verbose diagnostics on demand

Bites keep their one-line verdicts by default; `--verbose` asks them to also itemize what they measured (each clone, each dead-code issue), so nobody has to re-run the underlying tool locally to see what's bad.

### 16.13.1 prints a bite's verbose lines only when run with verbose
