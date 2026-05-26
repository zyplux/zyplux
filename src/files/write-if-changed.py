#!/usr/bin/env python3
"""Idempotent file writer for [bash.*] snippets: read stdin, write to the dest path only if bytes differ. Installed verbatim to /usr/local/bin; standalone python3 + stdlib only. Usage: <producer> | write-if-changed <dest-path> [octal-mode]."""

import sys
from pathlib import Path

dest = Path(sys.argv[1])
mode = int(sys.argv[2], 8) if len(sys.argv) > 2 else 0o644
content = sys.stdin.buffer.read()

if dest.exists() and dest.read_bytes() == content:
    print(f"Unchanged: {dest}")
    sys.exit(0)

print(f"Writing  : {dest}")
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_bytes(content)
dest.chmod(mode)
