# 2. [Viewing VS Code process load](test_2_viewing_vscode_process_load.py)

## 2.1 labeling a process by its role or owning extension

### 2.1.1 chromium process types map to friendly role names

### 2.1.2 an extension host is distinguished from a plain node service

### 2.1.3 network service processes are labeled

### 2.1.4 an unrecognized chromium type is shown as-is

### 2.1.5 the main process of a variant is labeled main

### 2.1.6 a user-installed extension process is labeled by its extension id

### 2.1.7 a builtin extension process is labeled distinctly from a user-installed one

### 2.1.8 a vs code helper process with no extension dir falls back to its script path

### 2.1.9 an unrelated process keeps its own process name

### 2.1.10 a process with no path-like argument falls back to its name

## 2.2 coloring rows and cells by cpu load

### 2.2.1 cpu percent maps to a busy yellow or idle color tier

### 2.2.2 extension and builtin roles get distinct colors

### 2.2.3 a busy row is highlighted, an idle row is dimmed

## 2.3 attributing an extension host's cpu to the owning extension

### 2.3.1 profiler hit counts are attributed and expressed as a percentage share

## 2.4 rendering the live view

### 2.4.1 an empty process list shows a friendly empty state

### 2.4.2 populated rows show pid, role, and attributed sub-rows

### 2.4.3 the interactive hint communicates profiling state and hidden row count

## 2.5 sampling the real process tree (against a faked psutil)

### 2.5.1 finds main processes by excluding ones whose own parent is also vscode

### 2.5.2 a main process survives a failed parent lookup

### 2.5.3 sample processes labels, sorts by cpu, and forgets dead pids

### 2.5.4 a process that dies mid-sample is dropped without derailing the scan

### 2.5.5 a process tree that vanishes mid-scan is skipped

### 2.5.6 only busy extension hosts are considered for profiling

### 2.5.7 visible row capacity never drops below the documented floor

### 2.5.8 raw keyboard and read key are no-ops outside a real tty

## 2.6 the cli

### 2.6.1 version flag prints the version and exits cleanly

### 2.6.2 a single snapshot runs end to end against the real machine
