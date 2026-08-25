"""Generate the Colab notebook that solves the Stage 8 3D model on a GPU.

Kept as a generator rather than a checked-in .ipynb, for the same reason as the
matrix notebook: the paths and the measured timings live in one place and
cannot drift from the rest of the repo.

Sizing, all measured rather than assumed:

    9.6 M cells x 4543 timesteps x 64 models = 2.79 M Mcell-steps
    36.9 Mcell/s on 12 laptop CPU threads  ->  21 h
    ~300 Mcell/s on a Colab T4             ->  2.6 h

which is why this runs on Colab at all.
"""
from __future__ import annotations

import json
from pathlib import Path

DRIVE = "/content/drive/MyDrive/bonesim"
CELLS_M = 9.6              # million, GridSpec3D default
TIMESTEPS = 4543
N_MODELS = 64              # 3 scenes x 21 positions + 1 reference
CPU_MCELLS = 36.9          # measured, 12 threads on the laptop
GPU_MCELLS = 300.0         # measured for gprMax on a T4

WORK = 1e6 * CELLS_M * TIMESTEPS * N_MODELS / 1e6 / 1e6   # Mcell-steps, 1e6
cpu_h = CELLS_M * 1e6 * TIMESTEPS * N_MODELS / (CPU_MCELLS * 1e6) / 3600
gpu_h = CELLS_M * 1e6 * TIMESTEPS * N_MODELS / (GPU_MCELLS * 1e6) / 3600


def md(text):
    return {"cell_type": "markdown", "metadata": {},
            "source": text.splitlines(True)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": text.splitlines(True)}


INTRO = f"""# bonesim - Stage 8, the 3D cylindrical limb

Every result in Stages 0-7 comes from a **2D TMz plane**, and "two dimensional
propagation" is listed as a limitation of the study. This notebook solves the
same detection problem on a genuinely **cylindrical** limb, so that limitation
can be tested rather than restated.

What changes, and why the answer is not obvious in advance:

| effect | direction |
|---|---|
| a curved skin surface spreads the reflected wavefront | costs signal |
| energy leaves the plane that 2D traps inside it | costs signal |
| a crack through a curved wall is a longer scattering edge, lit over a range of angles | **returns** signal |

**Sizing, measured rather than assumed.** {CELLS_M:.1f} M cells x {TIMESTEPS}
timesteps x {N_MODELS} models. At the **{CPU_MCELLS:.1f} Mcell/s** the laptop
manages on 12 threads that is **{cpu_h:.0f} h**; at the ~{GPU_MCELLS:.0f}
Mcell/s of a T4 it is **{gpu_h:.1f} h**. That gap is the whole reason for this
notebook.

**Resumable, per scene.** The four scenes are solved independently and a
finished one is skipped on a rerun. Resume is not per model: `gprMax -n 21`
reruns all 21 regardless of what is already on disk, so an interruption costs
the current scene, at most about 50 min.
"""

CHECK_GPU = '''import os
import subprocess

out = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
if out.returncode != 0:
    raise SystemExit(
        "No GPU attached. Runtime > Change runtime type > T4 GPU, then rerun.\\n"
        "Do NOT fall back to CPU here. Colab gives two vCPUs against the "
        "laptop's sixteen threads, so a CPU run would be slower than simply "
        "running it at home.")
print([l for l in out.stdout.split("\\n") if "MiB" in l or "Tesla" in l][:2])
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
# and a missing file here would fail once per model rather than once.
mats = SRC / "config" / "materials.in"
assert mats.exists() and "#add_dispersion_debye" in mats.read_text(), \\
    "config/materials.in missing or has no Debye cards"

out_dir = DRIVE / "stage8_3d"
out_dir.mkdir(parents=True, exist_ok=True)
print(f"unpacked {{len(list(SRC.rglob('*.py')))}} python files")
print(f"results directory {{out_dir}}")
print(f"already solved: {{len(list(out_dir.glob('*.out')))}} / {N_MODELS}")
'''

DECKS = '''# Writes the four input decks and re-runs every geometry check: domain
# margins, transverse width, and cells per wavelength at the gaussiandot band
# edge. Cheap here, and a rejected grid found now costs seconds rather than
# being discovered two hours into a solve.
!cd /content/bonesim && python scripts/run_stage8_3d.py --decks
'''

RUN = f'''import shutil
import subprocess
import time
from pathlib import Path

SRC = Path("/content/bonesim/runs/stage8_3d")
OUT = Path("{DRIVE}/stage8_3d")
SCRATCH = Path("/content/work3d")
SCRATCH.mkdir(exist_ok=True)

# Scratch stays on local Colab disk. gprMax writes and rewrites while solving
# and Drive is far slower for that; only the finished .out needs to survive.
#
# Resume granularity is the SCENE, not the model. "gprMax deck.in -n 21" runs
# all 21 and overwrites any existing output, so copying partial results back
# would achieve nothing - an earlier version of this cell did exactly that.
# A scene is at most about 50 min, and the whole run fits inside one session,
# so scene-level is enough.
JOBS = [("reference", 1), ("intact", 21), ("kerf10", 21), ("kerf20", 21)]

for stem, n in JOBS:
    have = len(list(OUT.glob(f"{{stem}}*.out")))
    if have >= n:
        print(f"{{stem}}: {{have}}/{{n}} already solved, skipping")
        continue
    shutil.copy(SRC / f"{{stem}}.in", SCRATCH / f"{{stem}}.in")

    print(f"{{stem}}: solving {{n}} models ...", flush=True)
    t0 = time.time()
    r = subprocess.run(
        ["python", "-u", "-m", "gprMax", f"{{stem}}.in", "-n", str(n), "-gpu"],
        cwd=SCRATCH, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
        raise SystemExit(f"{{stem}} failed")

    moved = 0
    for p in sorted(SCRATCH.glob(f"{{stem}}*.out")):
        shutil.copy(p, OUT / p.name)
        moved += 1
    print(f"{{stem}}: {{moved}} files in {{(time.time()-t0)/60:.1f}} min",
          flush=True)

print()
print("solved:", len(list(OUT.glob("*.out"))), "/", {N_MODELS})
'''

STATUS = f'''from pathlib import Path

OUT = Path("{DRIVE}/stage8_3d")
for stem, n in (("reference", 1), ("intact", 21), ("kerf10", 21),
                ("kerf20", 21)):
    have = len(list(OUT.glob(f"{{stem}}*.out")))
    mark = "done" if have >= n else "INCOMPLETE"
    print(f"  {{stem:<10}} {{have:>3}} / {{n:<3}}  {{mark}}")

total = len(list(OUT.glob("*.out")))
size = sum(p.stat().st_size for p in OUT.glob("*.out")) / 1e6
print()
print(f"  {{total}} / {N_MODELS} models, {{size:.1f}} MB")
if total >= {N_MODELS}:
    print()
    print("  Complete. Copy MyDrive/bonesim/stage8_3d back to the laptop into")
    print("  runs/stage8_3d/, then:")
    print("      python scripts/run_stage8_3d.py --analyse")
    print("      python scripts/run_band_study.py 3.0 6.0 '3D comparison band'")
    print()
    print("  The second command scores the 2D matrix over the SAME 3-6 GHz")
    print("  window. Comparing 3D at 3-6 GHz against 2D at 3-11 GHz would")
    print("  confound geometry with bandwidth, and the bandwidth study already")
    print("  showed bandwidth is worth 22.9 dB here - far more than any")
    print("  plausible geometric effect.")
'''

NOTES = f"""## Notes

**Why the band is 3-6 GHz and not 3-11.** A 3D grid fine enough for 11 GHz is
unaffordable: the 2D matrix used 0.2 mm cells, and the same resolution across a
76 mm width would be roughly 380 times larger. The grid here is 0.4 mm at a
4 GHz centre frequency, which gives 9.3 cells per wavelength in muscle at the
gaussiandot band edge.

Both 1.0 mm and 0.5 mm were tried and rejected by the mesh check. The check
itself had to be corrected first: it assumed the band ends at twice the centre
frequency, and gprMax reported a -4.81% phase-velocity error at 0.5 mm because
the pulse actually carries energy to about three times.

**Why the fracture widths are 1 and 2 mm.** At 0.4 mm cells the 0.2 mm kerf
cannot be represented. This model exists to test whether curvature and
out-of-plane scattering change the result, not whether a hairline crack
survives a coarser mesh.

**If the session dies.** Rerun the solve cell. Completed **scenes** are on
Drive and are skipped; a scene interrupted part-way is redone, because
`gprMax -n 21` reruns all 21 models regardless of what is already on disk.
The largest scene is about 50 min. Expect {gpu_h:.1f} h in total, against a
free-session cap near 12 h, so this should finish in one sitting.

**Do not run this on CPU.** {cpu_h:.0f} h on the laptop's twelve threads, and
Colab gives two vCPUs.
"""

cells = [
    md(INTRO),
    md("## 1. Confirm a GPU is attached"),
    code(CHECK_GPU),
    md("## 2. Mount Drive"),
    code(MOUNT),
    md("## 3. Build gprMax with CUDA\n\nAbout five minutes. Only needed once "
       "per session."),
    code(BUILD),
    md("## 4. Unpack bonesim from Drive"),
    code(UNPACK),
    md("## 5. Write the decks\n\nSolves nothing; confirms the geometry and "
       "grid pass every check."),
    code(DECKS),
    md(f"## 6. Solve\n\nAbout {gpu_h:.1f} h. Safe to interrupt, safe to "
       "rerun."),
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
       / "colab_stage8_3d.ipynb")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(nb, indent=1), encoding="utf-8")
print(f"wrote {out} ({len(cells)} cells)")
print(f"projected: {cpu_h:.0f} h local CPU, {gpu_h:.1f} h on a T4")
