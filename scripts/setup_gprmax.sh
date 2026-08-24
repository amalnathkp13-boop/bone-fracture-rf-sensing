#!/usr/bin/env bash
# Build gprMax from source against the bonesim conda environment.
# Run inside WSL2 Ubuntu. Idempotent: safe to re-run.
set -euo pipefail

CONDA_ROOT="${CONDA_ROOT:-$HOME/miniforge3}"
SRC="${SRC:-$HOME/src/gprMax}"
ENV_NAME="${ENV_NAME:-bonesim}"

# shellcheck disable=SC1091
source "$CONDA_ROOT/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

if [ ! -d "$SRC" ]; then
  mkdir -p "$(dirname "$SRC")"
  git clone https://github.com/gprMax/gprMax.git "$SRC"
fi

cd "$SRC"
echo "gprMax source: $(git rev-parse --short HEAD) on $(git rev-parse --abbrev-ref HEAD)"

# -march=native targets Zen 3 (AVX2). Drop it if the binary must be portable.
python setup.py build
python setup.py install

echo "=== verification ==="
python - <<'PY'
import gprMax, numpy, scipy, h5py, sys
print("python  ", sys.version.split()[0])
print("gprMax  ", getattr(gprMax, "__version__", "?"))
print("numpy   ", numpy.__version__)
print("scipy   ", scipy.__version__)
print("h5py    ", h5py.__version__)
PY
