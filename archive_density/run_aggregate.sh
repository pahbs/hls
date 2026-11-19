#!/bin/bash
# Start `hls_density.py aggregate <year>` for each year given, in the background on this node (run it on a forest node:
#   ssh forest202 /home/pmontesa/code/hls/archive_density/run_aggregate.sh 2025 2022 2019). Logs: $LOGS/aggregate_<year>.log
HERE=$(cd "$(dirname "$0")" && pwd)
PY=${PY:-/panfs/ccds02/app/modules/jupyter/ilab/tensorflow-kernel/bin/python}
LOGS=${LOGS:-/explore/nobackup/people/pmontesa/hls_archive_density/logs}
mkdir -p "$LOGS"
cd "$HERE" || exit 1
for y in "$@"; do
    setsid nohup "$PY" -u hls_density.py aggregate "$y" > "$LOGS/aggregate_$y.log" 2>&1 < /dev/null &
    echo "$(hostname -s): $y started"
done
