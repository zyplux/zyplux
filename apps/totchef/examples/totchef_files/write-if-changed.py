#!/usr/bin/env python3
"""Idempotent file writer for [bash.*] snippets: read stdin, write to the dest path only if bytes differ. Installed verbatim to /usr/local/bin; standalone python3 + stdlib only. Usage: <producer> | write-if-changed <dest-path> [octal-mode]."""

import argparse
import sys
from pathlib import Path

__version__ = "1.0.0"


def parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="write-if-changed", description="Read stdin and write it to dest only when the bytes differ: <producer> | write-if-changed <dest> [mode]"
    )
    parser.add_argument("dest", type=Path, help="file to write when stdin differs from its current bytes")
    parser.add_argument("mode", nargs="?", default="0644", help="octal file mode applied on write (default 0644)")
    parser.add_argument("--version", action="version", version=__version__)
    return parser.parse_args()


def main() -> None:
    args = parse_cli()
    content = sys.stdin.buffer.read()
    if args.dest.exists() and args.dest.read_bytes() == content:
        print(f"Unchanged: {args.dest}")
        return
    print(f"Writing  : {args.dest}")
    args.dest.parent.mkdir(parents=True, exist_ok=True)
    args.dest.write_bytes(content)
    args.dest.chmod(int(args.mode, 8))


if __name__ == "__main__":
    main()
