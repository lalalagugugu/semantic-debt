#!/bin/bash
# Run under: nohup caffeinate -i bash scripts/t29_u2_resume.sh <approved entry arguments> >> <private log> 2>&1 &
set -u
cd "$(dirname "$0")/.." || exit 4
while true; do
    uv run --offline python -u scripts/t29_u2.py "$@"
    status=$?
    case "$status" in
        0|4|5) exit "$status" ;; # complete, fingerprint/auth/config stop, or budget stop
        *) sleep 60 ;;          # network/process exit or peak hours: retry the same command
    esac
done
