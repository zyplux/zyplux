# 1. [Running just recipes under a logged PTY](test_1_running_just_recipes_under_a_logged_pty.py)

## 1.1 wrapping just so every run is logged

### 1.1.1 forwards arbitrary recipe args and propagates the exit code

### 1.1.2 announces the log path and points logs/just.log at the latest run

### 1.1.3 prunes all but the newest run logs

## 1.2 the version flag and a missing just binary

### 1.2.1 version flag prints the version and exits cleanly

### 1.2.2 a missing just binary fails fast with a clear message

## 1.3 keeping the transcript greppable across control sequences

### 1.3.1 carriage return overwrites replay as the final line

### 1.3.2 backspaces erase characters like a real progress bar

### 1.3.3 erase in line clears a redrawn progress message

### 1.3.4 cursor motion escapes flush the pending line

### 1.3.5 stray oscs and charset switches are swallowed rather than logged

### 1.3.6 cursor movement escapes reposition the write column

### 1.3.7 erase in line clears exactly the requested span

## 1.4 watching descriptors and forwarding resize/interrupt signals

### 1.4.1 a closed descriptor is reported as unwatchable

### 1.4.2 a non tty master fd does not crash the winsize copy

### 1.4.3 forwarded signals relay to the child's process group

## 1.5 streaming pty bytes to the terminal and log without a real pty

### 1.5.1 write all retries until every byte is written

### 1.5.2 read pty returns the chunk or empty bytes once the fd is closed

### 1.5.3 forward stdin relays a chunk and reports eof or a read error

### 1.5.4 relay tees cleaned bytes to the log and stdout until the master fd closes

## 1.6 orchestrating a run around a stubbed child process

### 1.6.1 copy winsize copies the real terminal size when stdout is a tty

### 1.6.2 raw stdin is a no-op when stdin is not a tty

### 1.6.3 run under pty wires spawn, signals, relay and the exit code together

### 1.6.4 link latest points logs/just.log at the given run log

### 1.6.5 run just writes the log header and footer and prunes stale logs

### 1.6.6 the CLI command exits with run just's status code
