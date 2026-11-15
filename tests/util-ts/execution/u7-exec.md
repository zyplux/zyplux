# u7. [Running a child process through the exec primitive](u7-exec.test.ts)

## u7.1 capturing process output

### u7.1.1 resolves with stdout, stderr, and the exit code

### u7.1.2 decodes text with an explicit encoding

## u7.2 configuring the spawn through chained calls

### u7.2.1 runs in a chained working directory

### u7.2.2 overlays chained environment variables onto the parent environment

## u7.3 feeding stdin and merging streams

### u7.3.1 pipes a provided stdin into the process

### u7.3.2 interleaves stdout and stderr when merge is requested

## u7.4 failing commands

### u7.4.1 rejects with an ExecError carrying the exit code

### u7.4.2 resolves a failing command when nothrow is chained

### u7.4.3 rejects when argv is empty

### u7.4.4 rejects when the command does not exist

### u7.4.5 rejects a command terminated by a signal

### u7.4.6 reports signal termination as failure when nothrow is chained

## u7.5 sharing the parent terminal

### u7.5.1 passes input and both output streams through the parent

### u7.5.2 runs in the requested working directory

### u7.5.3 rejects a nonzero exit

### u7.5.4 rejects a missing executable

### u7.5.5 rejects termination by a signal
