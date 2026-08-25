#!/bin/bash
set -u
export CSXCAD_INSTALL_PATH=/root/opt/openEMS
export LD_LIBRARY_PATH=/root/opt/openEMS/lib:${LD_LIBRARY_PATH:-}
export OMP_NUM_THREADS=8
cd /mnt/c/Users/ASUS/bonesim || exit 1
mkdir -p runs/feedtaper
PY=/root/opt/openEMS/venv/bin/python
for v in t275_l08 t275_l12 t350_l12; do
    echo "=== ${v} starting $(date +%H:%M:%S) ==="
    "${PY}" -u scripts/tune_feed_taper.py "${v}" > "runs/feedtaper/${v}.log" 2>&1
    echo "=== ${v} exit $? $(date +%H:%M:%S) ==="
done
echo ALLDONE
