#!/usr/bin/env bash
# Build openEMS with Python bindings, inside WSL2 Ubuntu.
#
# Deferred from Stage 0 on purpose: openEMS pulls Boost, VTK, CGAL and Qt5 and
# takes roughly 45 minutes to build, and nothing before Stage 5 needs it.
#
# It is used for one job only - characterising the antipodal Vivaldi antenna of
# proposal 2.3 (S11 across 3-11 GHz, radiation pattern, phase centre). gprMax
# remains the solver for everything else.
#
# Idempotent: safe to re-run.
set -euo pipefail

CONDA_ROOT="${CONDA_ROOT:-$HOME/miniforge3}"
ENV_NAME="${ENV_NAME:-bonesim}"
SRC="${SRC:-$HOME/src/openEMS-Project}"
PREFIX="${PREFIX:-$HOME/opt/openEMS}"

echo "=== 1. system dependencies ==="
export DEBIAN_FRONTEND=noninteractive
# unattended-upgrades holds the dpkg lock after a WSL restart; wait it out
# rather than forcing it.
for _ in $(seq 1 120); do
  fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || break
  sleep 5
done
apt-get update -qq
apt-get install -y -qq \
  build-essential cmake git \
  libhdf5-dev libvtk9-dev libvtk9-qt-dev \
  libboost-all-dev libcgal-dev libtinyxml-dev \
  qtbase5-dev qtbase5-dev-tools

echo "=== 2. source ==="
if [ ! -d "$SRC" ]; then
  mkdir -p "$(dirname "$SRC")"
  git clone --recursive https://github.com/thliebig/openEMS-Project.git "$SRC"
fi
cd "$SRC"
git submodule update --init --recursive
echo "openEMS-Project at $(git rev-parse --short HEAD)"

echo "=== 3. build the solver ==="
# shellcheck disable=SC1091
source "$CONDA_ROOT/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"
python -c "import sys; print('building against', sys.executable)"
./update_openEMS.sh "$PREFIX"

echo "=== 4. Python bindings ==="
# Built by hand rather than with update_OpenEMS.sh --python, for two reasons.
#
# First, --python installs the extensions into an isolated venv under the
# prefix, which is not where this project wants them: the antenna study has to
# import openEMS alongside numpy, h5py and the rest of the bonesim stack. Here
# they go into the conda environment directly.
#
# Second, both packages refuse to configure unless CSXCAD_INSTALL_PATH (or
# VIRTUAL_ENV) is set, and fail with a metadata-generation error that does not
# name the missing variable unless pip is run verbosely.
export CSXCAD_INSTALL_PATH="$PREFIX"
export OPENEMS_INSTALL_PATH="$PREFIX"
export CSXCAD_NOSCM=1 OPENEMS_NOSCM=1        # no git metadata needed
export LD_LIBRARY_PATH="$PREFIX/lib:${LD_LIBRARY_PATH:-}"
pip install -q setuptools_scm
for pkg in CSXCAD openEMS; do
  (cd "$SRC/$pkg/python" && pip install . --no-build-isolation -q)
  echo "  $pkg installed"
done

echo "=== 5. verify ==="
"$PREFIX/bin/openEMS" --version 2>&1 | head -3 || true
python - <<'PY'
import CSXCAD
import openEMS
print("CSXCAD ", getattr(CSXCAD, "__version__", "ok"))
print("openEMS", getattr(openEMS, "__version__", "ok"))
PY
echo "=== openEMS ready at $PREFIX ==="
