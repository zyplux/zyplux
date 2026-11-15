# a25. [Fingerprinting release contents](a25_content_hashes_test.py)

## a25.1 comparing package contents

### a25.1.1 ignores archive timestamps ordering and compression

### a25.1.2 detects packaged files permissions and metadata changes

### a25.1.3 covers both python distributions and ignores their listing order

### a25.1.4 filters archive files with configured includes

### a25.1.5 filters readme descriptions and derived wheel checksums

## a25.2 recording and verifying package fingerprints

### a25.2.1 initializes all target hashes and preserves manifest comments

### a25.2.2 rejects stale hashes before publishing

### a25.2.3 leaves the manifest unchanged when packaging fails

### a25.2.4 rejects invalid hash formats

### a25.2.5 rejects empty package builds

### a25.2.6 refreshes hashes after versioning and keeps repeated preparation stable

### a25.2.7 rejects missing fingerprints before publication

### a25.2.8 validates package fingerprints before repairing github releases

### a25.2.9 builds each package once when repairing a github release

### a25.2.10 rejects stale prepared dependencies before upload

### a25.2.11 rejects root package archives that include the release manifest

### a25.2.12 accepts development only metadata changes

## a25.3 discovering package impact through real builds

### a25.3.1 detects bundled shared changes and ignores unpacked files

## a25.4 fingerprinting actions and containers

### a25.4.1 covers implicit and explicit action sources

### a25.4.2 covers container inputs using build ignore rules

### a25.4.3 rejects stale action and container fingerprints before publication

### a25.4.4 rejects manual surface declarations

### a25.4.5 rejects action path declarations

### a25.4.6 hashes symlink identity including directory and broken links

### a25.4.7 selects individual files outside the action directory with includes

### a25.4.8 rejects action includes outside the repository

### a25.4.9 covers container build configuration with identical input files

### a25.4.10 fingerprints selected symlinks and selected target files

### a25.4.11 rejects missing container dockerfiles while preparing

### a25.4.12 fingerprints git ignored container inputs

### a25.4.13 prefers dockerfile adjacent ignore rules and fingerprints the rules

### a25.4.14 reports selected container inputs on fingerprint mismatch

### a25.4.15 requires container ignore rules to exclude git metadata

### a25.4.16 applies markdown selection to action and container inputs

### a25.4.17 fingerprints configured runtime major and minor versions only

### a25.4.18 rejects unknown minor version sources
