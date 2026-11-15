# a18. [Preparing reviewed releases](a18_prepare_release_test.py)

## a18.1 preparing native package releases

### a18.1.1 runs pnpm versioning and uv to produce synchronized versions changelogs and lockfiles

Preparation consumes each fragment once. A repeated preparation without new fragments leaves versions and changelogs unchanged.

### a18.1.2 rejects python version drift before changing any release files

### a18.1.3 stops before python synchronization when native versioning fails

### a18.1.4 propagates a workspace dependency bump through pnpm

### a18.1.5 directs version lookups to the package publication registry

### a18.1.6 authenticates private preparation with existing github credentials

### a18.1.7 preserves explicit registry authentication

### a18.1.8 keeps public preparation independent of github credentials

### a18.1.9 prepares without a github login when no fallback is available

### a18.1.10 rejects invalid authentication without disclosing credentials

### a18.1.11 adds only missing scope credentials and honors lowercase environment precedence

### a18.1.12 adds authentication without changing dependency registry routes

## a18.2 repeatable preparation

### a18.2.1 consolidates sequential and batched intents from one baseline

### a18.2.2 replans dependency bumps and preserves manifest source edits

### a18.2.3 restores release metadata and preserves user changes after failure

### a18.2.4 preserves metadata when a real prepack hook fails

### a18.2.5 starts a new baseline after publication

### a18.2.6 refuses to rewind a partially published preparation

### a18.2.7 requires the latest baseline when a newer version was published

### a18.2.8 requires legacy pending releases to publish before adoption

### a18.2.9 preserves overlapping manual release edits when replay conflicts

### a18.2.10 removes new release metadata on reported failure

### a18.2.11 freezes an action version tag before release finalization

### a18.2.12 preserves preparation inputs when authentication bootstrap fails

### a18.2.13 replays preparation after ledger formatting

### a18.2.14 keeps the record independent of published history and unchanged manifest fields

### a18.2.15 preserves unrelated python fields comments and historical notes

### a18.2.16 rejects overlapping fields entries and consumed intent names

### a18.2.17 converts full snapshot records without losing pending intents

### a18.2.18 removes the record when no pending metadata work remains

### a18.2.19 rewinds only prepared dependency fields and rejects conflicting ranges

### a18.2.20 prepares first releases with missing empty or title only changelogs
