# c3. [Reporting tracked repository metrics](c3_code_metrics_test.py)

## c3.1 measuring source content

### c3.1.1 splits typescript into prose code and branches

### c3.1.2 measures each supported grammar without network access

Tests use a deterministic byte tokenizer while exercising real grammar parsers. Normal reports use the o200k_base tokenizer.

### c3.1.3 keeps prose unknown languages and binaries distinct

### c3.1.4 rolls up typescript without counting it twice

## c3.2 selecting files

### c3.2.1 reads tracked worktree content without changing the index

### c3.2.2 excludes lockfiles deleted files and custom report destinations

### c3.2.3 uses shared source categories in scoped reports

## c3.3 reporting errors

### c3.3.1 reports empty scopes and missing repositories

## c3.4 Staged snapshots

### c3.4.1 Measures staged changes without including unstaged edits

Staged additions, modifications and deletions determine the report; partially staged working files and the index remain untouched.

### c3.4.2 Uses staged classification and excludes the report

Classification uses the staged config, and the report excludes itself.

### c3.4.3 Handles staged deletion of the last file

An empty staged snapshot produces zero totals.

### c3.4.4 Preserves report when staged classification is invalid

Generation fails without overwriting the report or changing the index.
