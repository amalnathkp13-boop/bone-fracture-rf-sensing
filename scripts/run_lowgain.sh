#!/bin/bash
set -u
export CSXCAD_INSTALL_PATH=/root/opt/openEMS
export LD_LIBRARY_PATH=/root/opt/openEMS/lib:${LD_LIBRARY_PATH:-}
export OMP_NUM_THREADS=8
cd /mnt/c/Users/ASUS/bonesim || exit 1
mkdir -p runs/gain
/root/opt/openEMS/venv/bin/python -u scripts/tune_low_gain.py \
    > runs/gain/ap70.log 2>&1
echo "exit $?"
