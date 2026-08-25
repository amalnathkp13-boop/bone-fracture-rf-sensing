#!/bin/bash
# Runs the corrugation retry inside WSL, where openEMS lives.
#
# A shell script file rather than an inlined `wsl -- bash -lc "for ..."`:
# passing a loop variable through Git Bash into WSL silently ate the "$v",
# so every variant ran with no argument and simulated nothing while still
# exiting 0. A file has no quoting layers to lose.
set -u
export CSXCAD_INSTALL_PATH=/root/opt/openEMS
export LD_LIBRARY_PATH=/root/opt/openEMS/lib:${LD_LIBRARY_PATH:-}
export OMP_NUM_THREADS=8

cd /mnt/c/Users/ASUS/bonesim || exit 1
mkdir -p runs/corrugations
PY=/root/opt/openEMS/venv/bin/python

for v in plain_e3 corr4_d4 corr6_d6; do
    echo "=== ${v} starting $(date +%H:%M:%S) ==="
    "${PY}" -u scripts/retry_corrugations.py "${v}" \
        > "runs/corrugations/${v}.log" 2>&1
    echo "=== ${v} exit $? $(date +%H:%M:%S) ==="
    tail -4 "runs/corrugations/${v}.log"
done
echo ALLDONE
