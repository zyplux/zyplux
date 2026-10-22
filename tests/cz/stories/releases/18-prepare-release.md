# 18. [Preparing reviewed releases](18-prepare-release.test.ts)

## 18.1 preparing native package releases

### 18.1.1 runs Changesets and uv to produce synchronized versions, changelogs and lockfiles

Preparation consumes each fragment once. A repeated preparation without new fragments fails without advancing the prepared versions.

### 18.1.2 rejects Python version drift before changing any release files
