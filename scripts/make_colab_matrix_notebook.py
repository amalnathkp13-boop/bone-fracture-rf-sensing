"""Generate the Colab notebook that solves the experiment matrix on a GPU.

Kept as a generator rather than a checked-in .ipynb so the paths and the
measured timings live in one place and cannot drift from the rest of the repo.
"""
from __future__ import annotations

import json
from pathlib import Path

DRIVE = "/content/drive/MyDrive/bonesim"
LOCAL_CPU_MIN = 17          # measured median, min per cell on the laptop
GPU_SPEEDUP = 7.18          # measured, docs/colab.md
N_CELLS = 192


def md(text):
    return {"cell_type": "markdown", "metadata": {},
            "source": text.splitlines(True)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": text.splitlines(True)}


gpu_hours = N_CELLS * LOCAL_CPU_MIN / 60 / GPU_SPEEDUP
cpu_hours = N_CELLS * LOCAL_CPU_MIN / 60

INTRO = f"""# bonesim - experiment matrix on a Colab GPU

Solves the {N_CELLS}-acquisition matrix of proposal section 4.4 on an NVIDIA
GPU. gprMax ships a CUDA solver; the development laptop has an AMD card and
cannot use it.

Measured: **{LOCAL_CPU_MIN} min per cell** on the laptop, and the GPU is
**{GPU_SPEEDUP}x** faster on this model. So roughly **{cpu_hours:.0f} h here
against {gpu_hours:.1f} h on a T4**.

**Everything is resumable.** One cell is one file on Drive. Anything already
there is skipped, so if the session is reclaimed - and a free one will be -
just reopen this notebook and run it again. Nothing is lost but the cell that
was in flight.

### Before you start

1. On the laptop, run `python scripts/package_for_colab.py`
2. Upload the resulting `bonesim_colab.zip` to Drive as
   `MyDrive/bonesim/bonesim_colab.zip`
3. Here: **Runtime > Change runtime type > T4 GPU**
4. Run all cells

Results land in `MyDrive/bonesim/matrix/` as one `.npz` per acquisition, about
140 kB each - roughly 27 MB for the whole matrix. Analysis happens back on the
laptop; only the solve moves.
"""

CHECK_GPU = '''import os
import subprocess

out = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
if out.returncode != 0:
    raise SystemExit(
        "No GPU attached. Runtime > Change runtime type > T4 GPU, then rerun.\\n"
        "Do NOT fall back to CPU here: Colab gives two vCPUs against the "
        "laptop's sixteen threads, so a CPU run would be several times slower "
        "than simply running it at home.")
print(out.stdout.split("\\n")[8] if len(out.stdout.split("\\n")) > 8
      else out.stdout)
print("CPU cores:", os.cpu_count())
'''

MOUNT = '''from google.colab import drive

drive.mount("/content/drive")
'''

BUILD = '''%%bash
set -e
pip install -q "cython>=3.0" numpy scipy h5py matplotlib psutil colorama \\
    terminaltables tqdm scikit-learn 2>&1 | tail -1
pip install -q pycuda 2>&1 | tail -1

if [ ! -d /content/gprMax ]; then
  git clone -q https://github.com/gprMax/gprMax.git /content/gprMax
fi
cd /content/gprMax
python setup.py build 2>&1 | tail -1
pip install -e . --no-build-isolation -q 2>&1 | tail -1
python -c "import gprMax, pycuda.driver as d; d.init(); print('gprMax', gprMax.__version__, '| GPU', d.Device(0).name())"
'''

UNPACK = f'''import zipfile
from pathlib import Path

DRIVE = Path("{DRIVE}")
SRC = Path("/content/bonesim")
zip_path = DRIVE / "bonesim_colab.zip"

if not zip_path.exists():
    raise SystemExit(
        f"{{zip_path}} not found.\\n"
        "Run scripts/package_for_colab.py on the laptop and upload the zip "
        "to that path on Drive.")

SRC.mkdir(exist_ok=True)
with zipfile.ZipFile(zip_path) as z:
    z.extractall(SRC)

# The Debye fits from Stage 1. The deck builder refuses to run without them,
# and a missing file here would fail 192 times rather than once.
mats = SRC / "config" / "materials.in"
assert mats.exists() and "#add_dispersion_debye" in mats.read_text(), \\
    "config/materials.in missing or has no Debye cards"

out_dir = DRIVE / "matrix"
out_dir.mkdir(parents=True, exist_ok=True)
done = len(list(out_dir.glob("*.npz")))
print(f"unpacked {{len(list(SRC.rglob('*.py')))}} python files")
print(f"results directory {{out_dir}}")
print(f"already solved: {{done}} / {N_CELLS}")
'''

PLAN = '''!cd /content/bonesim && python scripts/run_matrix.py \\
    --out "{drive}/matrix" --dry-run 2>&1 | head -20
'''.format(drive=DRIVE)

RUN = f'''# Scratch stays on local Colab disk, not Drive: gprMax writes many small
# files per cell and Drive is far slower for that. Only the finished .npz needs
# to survive the session, and that goes to Drive.
#
# --max-hours stops cleanly rather than being killed part-way through a cell.
# Raise it if you have Pro; a free session caps near 12 h.
!cd /content/bonesim && python -u scripts/run_matrix.py \\
    --out "{DRIVE}/matrix" \\
    --scratch /content/work \\
    --gpu \\
    --max-hours 10
'''

STATUS = f'''from pathlib import Path

out = Path("{DRIVE}/matrix")
done = sorted(p.stem for p in out.glob("*.npz"))
print(f"{{len(done)}} / {N_CELLS} acquisitions solved")
if len(done) < {N_CELLS}:
    print("\\nRerun the previous cell to continue. Nothing is repeated.")
else:
    print("\\nMatrix complete. Copy MyDrive/bonesim/matrix back to the laptop")
    print("and run the Stage 7 analysis there.")

# What is finished, by fracture state and overlay.
from collections import Counter
by_state = Counter(k.split("_")[1] for k in done)
by_overlay = Counter(k.split("_ov")[1] for k in done)
print("\\nby state:  ", dict(sorted(by_state.items())))
print("by overlay:", dict(sorted(by_overlay.items())))
'''

NOTES = f"""## Notes

**If a session dies**, reopen and run all cells. The build takes a few minutes,
then the run picks up from the first unsolved acquisition. At {gpu_hours:.1f} h
of solve you should expect at least one interruption on the free tier.

**Do not run this on CPU.** Colab gives two vCPUs against the laptop's sixteen
threads, so a CPU run here is several times slower than simply running it at
home. The GPU is the entire reason to be here, and the first cell fails loudly
rather than silently falling back.

**Scratch is local, results are on Drive.** gprMax writes many small files per
cell and Drive is slow for that; only the finished `.npz` needs to persist. The
cost is that an interrupted cell restarts from the beginning - about two minutes
on a GPU - rather than resuming mid-scan.

**Only the solve moves.** Geometry, material fitting, the processing chain and
the statistics all stay on the laptop, where iteration is fast and there are no
session limits.
"""

cells = [
    md(INTRO),
    md("## 1. Confirm a GPU is attached"),
    code(CHECK_GPU),
    md("## 2. Mount Drive\n\nResults are written here so they survive the "
       "session being reclaimed."),
    code(MOUNT),
    md("## 3. Build gprMax with CUDA support\n\nFrom source, because the "
       "Cython extensions must match this runtime's Python and NumPy. A few "
       "minutes."),
    code(BUILD),
    md("## 4. Unpack bonesim from Drive"),
    code(UNPACK),
    md("## 5. Check the plan\n\nSolves nothing; confirms the matrix builds and "
       "reports what is outstanding."),
    code(PLAN),
    md(f"## 6. Solve\n\nAbout {gpu_hours:.1f} h for a full matrix. Safe to "
       "interrupt, safe to rerun."),
    code(RUN),
    md("## 7. Status"),
    code(STATUS),
    md(NOTES),
]

nb = {
    "nbformat": 4, "nbformat_minor": 0,
    "metadata": {
        "colab": {"provenance": [], "gpuType": "T4"},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
        "accelerator": "GPU",
    },
    "cells": cells,
}

out = (Path(__file__).resolve().parent.parent / "notebooks"
       / "colab_matrix.ipynb")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(nb, indent=1), encoding="utf-8")
print(f"wrote {out} ({len(cells)} cells)")
print(f"projected: {cpu_hours:.0f} h local, {gpu_hours:.1f} h on a T4")
