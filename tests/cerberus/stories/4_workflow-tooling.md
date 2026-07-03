# 4. [Keeping workflows on the workspace toolchain](test_4_workflow-tooling.py)

## 4.1 flagging workflows that install extra tools

### 4.1.1 flags a github action that sets up a disallowed tool

### 4.1.2 flags a github action recognized by the install action naming convention

### 4.1.3 flags a shell command that installs a tool

### 4.1.4 flags apt install with flags before the subcommand

### 4.1.5 flags piping a downloaded script into a shell

## 4.2 avoiding false positives on legitimate workflow steps

### 4.2.1 passes when workflows only set up the workspace toolchain

### 4.2.2 does not flag npm publish as a tool install

### 4.2.3 does not flag a download that never reaches a shell

## 4.3 scoping the scan to repos with workflows

### 4.3.1 skips repos with no workflow files to scan

## 4.4 handling unreadable workflow files

### 4.4.1 errors when a workflow file is not valid yaml
