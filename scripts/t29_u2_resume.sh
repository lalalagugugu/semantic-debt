#!/bin/bash
# Run under: nohup caffeinate -i bash scripts/t29_u2_resume.sh <approved entry arguments> >> <private log> 2>&1 &
set -u
cd "$(dirname "$0")/.." || exit 4
run_dir=runs/20261031-T29-u2-v3-01
done_count() { cat "$run_dir"/*.jsonl 2>/dev/null | grep -c '"status": "done"'; }
is_peak() {
    local day hour
    day=$(TZ=Asia/Shanghai date +%u)
    hour=$((10#$(TZ=Asia/Shanghai date +%H)))
    [ "$day" -le 5 ] && { [ "$hour" -ge 9 ] && [ "$hour" -lt 12 ] || [ "$hour" -ge 14 ] && [ "$hour" -lt 18 ]; }
}
stalled=0
last=$(done_count)
while true; do
    uv run --offline python -u scripts/t29_u2.py "$@"
    status=$?
    case "$status" in
        0|4|5) exit "$status" ;; # complete, fingerprint/auth/config stop, or budget stop
    esac
    now=$(done_count)
    if [ "$now" -gt "$last" ] || is_peak; then
        stalled=0
    else
        stalled=$((stalled + 1))
    fi
    last=$now
    if [ "$stalled" -ge 3 ]; then
        echo "no new attempts in 3 rounds; stopping for a look" >&2
        exit 6
    fi
    sleep 60                     # network/process exit or peak hours: retry the same command
done
