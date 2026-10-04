# Roadmap: safe release selection in `cz upgrade`

Status: proposed.

## Finding

`minimumReleaseAge` is a supply-chain quarantine, not a general dependency-stability policy. pnpm applies one age to direct and transitive dependencies so a compromised release has time to be detected and removed; the npm ecosystem commonly detects such releases within hours. SemVer does not measure trust: a malicious release can be a patch just as easily as a minor or major. Making patches immediate would therefore remove much of the protection.

A fixed delay can nevertheless mishandle ordinary bug fixes if an updater selects the newest *mature* version. If `1.1.0` is released at hour 0 and `1.1.1` fixes it at hour 12, a 24-hour per-version delay makes `1.1.0` eligible from hour 24 to 36 while the fix remains quarantined. That preserves the original 12-hour bug-risk window, merely shifting it.

The correct selection rule is **latest or skip**, not **newest mature**. At hour 24 the actual latest version is still `1.1.1`, so the updater must leave the package unchanged. At hour 36 it can upgrade directly to `1.1.1`.

## Current Zyplux behavior

`cz upgrade` runs `pnpm update --recursive --include-workspace-root --latest`. Zyplux explicitly sets `minimumReleaseAge: 1440`, which makes pnpm's strict release-age mode the default. pnpm currently aborts an update when a newer target is still quarantined instead of skipping that package and continuing; its fallback behavior also has open edge cases around eligible intermediate versions. The shifted-risk scenario is therefore not a dependable description of today's command, but the all-or-nothing failure is inefficient for a large workspace.

## Decision

Keep the uniform 24-hour pnpm policy as the resolver-level security boundary. Do not encode `patch: 0`, `minor: 12h`, `major: 12h` as the security policy: pnpm has no such setting, it would leave transitive patches unguarded if emulated by disabling pnpm's policy, and release type is unrelated to compromise risk.

Move upgrade ergonomics into `cz upgrade`:

1. Read each direct dependency's real `latest` target and publish time.
2. If that target is younger than the repository's `minimumReleaseAge`, skip the whole dependency; never substitute an older mature release.
3. Pass only eligible dependency names to one pnpm update, leaving pnpm to enforce the same quarantine across the resulting transitive graph.
4. Report skipped packages with target version and remaining quarantine time, then continue upgrading everything else.
5. Keep fresh security fixes as an explicit, exact `package@version` approval path. Never create an external package- or scope-wide exclusion; the approval must remain reproducible until the lockfile passes normal verification after the release matures.

Add `trustPolicy: no-downgrade` separately after compatibility testing. It complements age quarantine by rejecting a drop in publishing trust evidence; it does not solve the bug-fix timing problem.

## Acceptance stories

- With a bad minor at hour 0 and its patch at hour 12, a run at hour 24 skips that dependency but upgrades other eligible dependencies; a run at hour 36 upgrades directly to the patch.
- A fresh patch is quarantined by default, proving that release type does not bypass the supply-chain policy.
- A reviewed exact security-fix exception succeeds without permitting other versions or transitive packages.
- Interactive and package-filtered upgrades use the same eligibility decision and explain every skip.

Use deterministic registry-packument fixtures in the existing `cz upgrade` story rather than real publication times.

## Research notes

- [pnpm documents `minimumReleaseAge` as mitigation for compromised packages](https://pnpm.io/supply-chain-security), and [applies it to direct and transitive dependencies](https://pnpm.io/settings/dependency-resolution#minimumreleaseage).
- [pnpm strict mode fails when no requested version is mature](https://pnpm.io/settings/dependency-resolution#minimumreleaseagestrict); [pnpm issue #11165](https://github.com/pnpm/pnpm/issues/11165) tracks making bulk update skip quarantined packages instead of aborting.
- [Dependabot supports SemVer-specific cooldowns](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#cooldown), but that is an update-scheduling feature and security updates bypass it.
- [Renovate ages each version separately](https://docs.renovatebot.com/key-concepts/minimum-release-age/#what-happens-if-a-package-has-multiple-updates-available), which demonstrates the shifted-window behavior this design avoids.
