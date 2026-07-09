# 28. [Capping copy-paste duplication via jscpd](test_28_jscpd.py)

## 28.1 enforcing the duplication threshold per language from jscpd's json report

### 28.1.1 passes when every language stays under the duplication threshold

### 28.1.2 fails when one language exceeds the threshold even though the total is under

### 28.1.3 fails with the exit code when jscpd itself exits non zero

### 28.1.4 errors when bunx is not on PATH

### 28.1.5 errors when jscpd writes no readable json report

## 28.2 surfacing the measured duplication

### 28.2.1 reports duplicated tokens and percentage per language

### 28.2.2 reads reports with flat per-language stats

### 28.2.3 leaves the detail unset on failure so the stats appear only in the fail line

## 28.3 sourcing the threshold and file selection from cerberus configuration

### 28.3.1 scans the repo root with the default selection and cwd shielded from repo config

### 28.3.2 enforces a configured threshold per language

### 28.3.3 defaults the threshold to zero point one percent when the config omits it

### 28.3.4 passes a configured pattern and ignore through to jscpd

## 28.4 scoping the scan to workspace-registered code

### 28.4.1 scans only the directories the workspace manifests register

### 28.4.2 falls back to the repo root when no manifest declares workspaces

### 28.4.3 errors when package.json is not valid JSON instead of crashing

### 28.4.4 errors when pyproject.toml is not valid TOML instead of crashing

## 28.5 itemizing clones in verbose runs

A passing run can still hide clones sitting under the threshold; in verbose mode the check lists every clone with both spans, the same lines a failure prints.

### 28.5.1 lists every clone as verbose lines when a verbose run passes

### 28.5.2 leaves the verbose lines empty without verbose

## 28.6 running jscpd at the version pinned in cerberus source

A bare `bunx jscpd` floats to npm's latest and drifts per machine; the check invokes the exact version pinned in cerberus's `tool_pins` module, so every run — local or CI, any repo — measures with the same tool.

### 28.6.1 invokes jscpd at the pinned version
