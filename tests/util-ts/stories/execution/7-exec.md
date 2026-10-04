# 7. [Running a child process through the exec primitive](7-exec.test.ts)

## 7.1 capturing process output

### 7.1.1 resolves with stdout, stderr, and the exit code

### 7.1.2 decodes text with an explicit encoding

## 7.2 configuring the spawn through chained calls

### 7.2.1 runs in a chained working directory

### 7.2.2 overlays chained environment variables onto the parent environment

## 7.3 feeding stdin and merging streams

### 7.3.1 pipes a provided stdin into the process

### 7.3.2 interleaves stdout and stderr when merge is requested

## 7.4 failing commands

### 7.4.1 rejects with an ExecError carrying the exit code

### 7.4.2 resolves a failing command when nothrow is chained

### 7.4.3 rejects when argv is empty

### 7.4.4 rejects when the command does not exist
