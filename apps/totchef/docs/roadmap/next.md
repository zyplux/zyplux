# Next.md

## 1. CookBase needs_binaries, installs_binaries

- (1) base cook should have needs_binaries and installs_binaries fields, which can be overridden/hardcoded in specific cooks
- these fields can also be configured in the totchef_recipe.toml to add to the hardcoded lists
- for example: apt_pkg cook already knows which binaries it's going to install - basically the packages - so could produce them as installs_binaries
- I think bin_cook(s) also know which binaries they install
- other cooks may not be that deterministic, so user can declare installs_binaries in the recipe
- (2) all the cooks already know which binaries they need as they do find_binary calls
- therefore each cook can hardcode required binaries list, then:
  - runtime: check if it's available
  - linttime: check if it will be installed upsteam via the depends_on
- (3) having binary list allows to
  - lint recipe and determine if all cooks will get their prerequisites
  - drop depends_on for binary-dependency cases (or replace with more specific needs_binaries)

## 2. totchef.lock

Consider a lockfile with sections for each cook for various scenarios like:
- save last run hash/version/timing info
- installed versions
- version pins
- drift detection
- uninstall functionality
- upgrade/downgrade
- etc.

## 3. publish totchef on pypi

Pre-publish checklist:

- [ ] ensure well structured docs, examples, motivation and purpose
- [ ] linting with `--fix` auto-fix
- [ ] scaffolding with `totchef init`
- [ ] each cook should provide usage help/examples via totchef cli
- [ ] commercial grade pretty
  - [ ] tui: (use cli builder app?)
  - [ ] github readme
  - [ ] website page
- [ ] lock bundled dep versions (such as nala) to ensure all's stable
- [ ] support node.js (or whenever relying on bun, do so via symlinked paths)

### 3.1 fresh machine

- [ ] smooth experience fresh box (container or virtual box testing)
- [ ] `totchef plan` should pass on fresh box when nothing installed
