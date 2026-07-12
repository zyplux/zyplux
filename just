#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p logs
script -qec "$(printf '%q ' command just "$@")" /dev/null | tee logs/just.log
status=${PIPESTATUS[0]}
sed -i -E $'s/\x1b\\[[0-9;]*[A-Za-z]//g; s/\x1b\\][^\x07]*\x07//g; s/\r$//; s/.*\r//' logs/just.log
exit "$status"
