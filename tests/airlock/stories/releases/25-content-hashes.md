# 25. [Fingerprinting release contents](test_25_content_hashes.py)

## 25.1 comparing package contents

### 25.1.1 ignores archive timestamps ordering and compression

### 25.1.2 detects packaged files permissions and metadata changes

### 25.1.3 covers both python distributions and ignores their listing order

## 25.2 recording and verifying package fingerprints

### 25.2.1 initializes all target hashes and preserves manifest comments

### 25.2.2 rejects stale hashes before publishing

### 25.2.3 leaves the manifest unchanged when packaging fails

### 25.2.4 rejects invalid hash formats

### 25.2.5 rejects empty package builds

### 25.2.6 refreshes hashes after versioning and keeps repeated preparation stable

### 25.2.7 rejects missing fingerprints before publication

### 25.2.8 validates package fingerprints before repairing github releases

### 25.2.9 builds each package once when repairing a github release

### 25.2.10 rejects missing or stale prepared dependencies before upload

## 25.3 discovering package impact through real builds

### 25.3.1 detects bundled shared changes and ignores unpacked files

## 25.4 fingerprinting actions and containers

### 25.4.1 covers the action directory and versioned implementation

### 25.4.2 covers container inputs using build ignore rules

### 25.4.3 rejects stale action and container fingerprints before publication

### 25.4.4 rejects manual surface declarations

### 25.4.5 requires repository relative action paths

### 25.4.6 hashes symlink identity including directory and broken links

### 25.4.7 covers declared action runtime files

### 25.4.8 rejects missing or external action runtime files

### 25.4.9 covers container build configuration with identical input files
