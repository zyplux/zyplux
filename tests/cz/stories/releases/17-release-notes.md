# 17. [Reviewed release notes](17-release-notes.test.ts)

## 17.1 listing prepared releases

### 17.1.1 emits version-specific notes and target metadata without registry access

### 17.1.2 preserves Markdown examples and excludes neighboring release versions

## 17.2 validating release preparation

### 17.2.1 validates prepared releases without writes or network requests

### 17.2.2 rejects unconsumed fragments

### 17.2.3 rejects a changelog with missing or empty notes

### 17.2.4 rejects inconsistent Python tracking manifests

## 17.3 publishing reviewed notes

### 17.3.1 sends the exact target entry to GitHub

### 17.3.2 rejects missing notes before publication
