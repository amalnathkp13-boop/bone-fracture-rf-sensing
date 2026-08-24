"""Generate the Colab GPU benchmark notebook.

Written as a generator rather than a checked-in .ipynb so the benchmark models
and the local reference numbers live in one place and cannot drift apart.
"""
from __future__ import annotations

import json
from pathlib import Path

# Local reference numbers, all measured. See docs/compute-budget.md.
LOCAL_NONDISP = 178e6      # cell-updates/s, 4 processes x 4 threads
LOCAL_DISP = 74e6          # cell-updates/s, production model with Debye tissue
LOCAL_BSCAN_S = 610.0      # one 61-position B-scan plus its reference
MATRIX_BSCANS = 192


def md(text):
    return {"cell_type": "markdown", "metadata": {},
            "source": text.splitlines(True)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": text.splitlines(True)}


INTRO = f"""# bonesim - Colab GPU benchmark

Decides one question: **is a hosted NVIDIA GPU faster than the local laptop for
this project's gprMax workload?**

gprMax ships a CUDA solver behind a `-gpu` flag. The development laptop has an
AMD RX 6800M, so that solver is unreachable there and every local figure is
CPU-only. A Colab GPU can run it.

One trade to keep in view: Colab's free tier gives about **2 vCPUs** against the
laptop's **16 threads**, so a CPU-only run here will be *slower* than the
laptop. The GPU is the entire reason to be here.

Local numbers to beat, all measured:

| workload | local |
|---|---|
| benchmark model, no dispersion | {LOCAL_NONDISP / 1e6:.0f} M cell-updates/s |
| production model, 6 Debye tissues | {LOCAL_DISP / 1e6:.0f} M cell-updates/s |
| one 61-position B-scan | {LOCAL_BSCAN_S:.0f} s |
| full matrix ({MATRIX_BSCANS} B-scans) | {MATRIX_BSCANS * LOCAL_BSCAN_S / 3600:.1f} h |

Run the cells in order; about 15 minutes, most of it building gprMax.

**Set a GPU runtime first:** Runtime > Change runtime type > T4 GPU.
"""

CHECK_GPU = '''import os
import subprocess

out = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
if out.returncode != 0:
    raise SystemExit(
        "No GPU attached. Runtime > Change runtime type > T4 GPU, then rerun.")
print(out.stdout)
print("CPU cores available:", os.cpu_count())
'''

BUILD = '''%%bash
set -e
pip install -q "cython>=3.0" numpy scipy h5py matplotlib psutil colorama \\
    terminaltables tqdm 2>&1 | tail -2
if [ ! -d /content/gprMax ]; then
  git clone -q https://github.com/gprMax/gprMax.git /content/gprMax
fi
cd /content/gprMax
python setup.py build 2>&1 | tail -3
pip install -e . --no-build-isolation -q 2>&1 | tail -2
python -c "import gprMax; print('gprMax', gprMax.__version__)"
'''

PYCUDA = '''!pip install -q pycuda 2>&1 | tail -3

import pycuda.driver as drv

drv.init()
dev = drv.Device(0)
print("GPU:", dev.name())
print("compute capability: %d.%d" % dev.compute_capability())
print("memory: %.1f GB" % (dev.total_memory() / 1e9))
'''

MODEL_A = """#title: non-dispersive throughput benchmark
#domain: 0.140 0.100 0.0002
#dx_dy_dz: 0.0002 0.0002 0.0002
#time_window: 3e-9

#material: 5.0 0.6 1 0 fatlike
#material: 42 6.0 1 0 musclelike
#material: 12 0.4 1 0 bonelike

#box: 0 0.030 0 0.140 0.070 0.0002 musclelike
#box: 0 0.070 0 0.140 0.074 0.0002 fatlike
#cylinder: 0.070 0.050 0 0.070 0.050 0.0002 0.010 bonelike

#waveform: gaussiandot 1 7e9 pulse
#hertzian_dipole: z 0.070 0.086 0 pulse
#rx: 0.070 0.086 0
"""

MODEL_B = """#title: production model, dispersive tissues
#domain: 0.1000 0.0550 0.0002
#dx_dy_dz: 0.0002 0.0002 0.0002
#time_window: 2.5e-09

#material: 4.57196 0.713624 1 0 skin_dry
#add_dispersion_debye: 2 32.3758 7.43609e-12 3.66933 7.9816e-11 skin_dry
#material: 3.01149 0.0476365 1 0 fat
#add_dispersion_debye: 2 1.85023 8.1162e-12 0.516319 2.89757e-11 fat
#material: 9.20366 0.867599 1 0 muscle
#add_dispersion_debye: 2 39.6209 7.56898e-12 5.05775 2.79524e-11 muscle
#material: 3.69273 0.118373 1 0 cortical_bone
#add_dispersion_debye: 2 5.62145 1.04285e-11 2.75291 3.42853e-11 cortical_bone
#material: 3.0272 0.0374966 1 0 marrow
#add_dispersion_debye: 2 1.86144 8.27295e-12 0.510127 3.00951e-11 marrow
#material: 9.14071 1.43319 1 0 blood
#add_dispersion_debye: 2 43.9658 8.41017e-12 6.82598 2.90441e-11 blood

#box: 0.0000 0.0350 0 0.1000 0.0370 0.0002 skin_dry
#box: 0.0000 0.0320 0 0.1000 0.0350 0.0002 fat
#box: 0.0000 0.0310 0 0.1000 0.0320 0.0002 muscle
#box: 0.0000 0.0270 0 0.1000 0.0310 0.0002 cortical_bone
#box: 0.0000 0.0170 0 0.1000 0.0270 0.0002 marrow
#box: 0.0000 0.0130 0 0.1000 0.0170 0.0002 cortical_bone
#box: 0.0495 0.0270 0 0.0505 0.0310 0.0002 blood

#waveform: gaussiandot 1 7e9 pulse
#hertzian_dipole: z 0.0200 0.0490 0 pulse
#rx: 0.0200 0.0490 0
"""

WRITE_MODELS = (
    "from pathlib import Path\n\n"
    'W = Path("/content/work")\n'
    "W.mkdir(exist_ok=True)\n\n"
    "MODEL_A = r" + repr(MODEL_A) + "\n\n"
    "MODEL_B = r" + repr(MODEL_B) + "\n\n"
    '(W / "model_a.in").write_text(MODEL_A)\n'
    '(W / "model_b.in").write_text(MODEL_B)\n\n'
    '# Cell counts and iteration counts, so throughput is comparable.\n'
    'CELLS = {"model_a": 700 * 500, "model_b": 500 * 275}\n'
    'ITERS = {"model_a": 6361, "model_b": 5299}\n'
    "for k in CELLS:\n"
    '    print("%s: %d cells x %d iterations = %.2e cell-updates"\n'
    "          % (k, CELLS[k], ITERS[k], CELLS[k] * ITERS[k]))\n"
)

RUN = '''import re
import subprocess
import time


def run(model, gpu):
    """Return (solver_seconds, None) or (None, error_tail)."""
    cmd = ["python", "-m", "gprMax", model + ".in"] + (["-gpu"] if gpu else [])
    t0 = time.time()
    p = subprocess.run(cmd, cwd="/content/work", capture_output=True, text=True)
    dt = time.time() - t0
    if p.returncode != 0:
        tail = (p.stdout + p.stderr).strip().splitlines()[-8:]
        return None, "\\n".join(tail)
    # Prefer the solver time gprMax reports over wall clock, which includes
    # model build and, on the GPU, kernel compilation.
    m = re.search(r"Solving time \\[HH:MM:SS\\]: (\\d+):(\\d+):([\\d.]+)", p.stdout)
    if m:
        h, mm, s = m.groups()
        dt = int(h) * 3600 + int(mm) * 60 + float(s)
    return dt, None


results = {}
for model in ("model_a", "model_b"):
    for gpu in (False, True):
        tag = model + (" GPU" if gpu else " CPU")
        dt, err = run(model, gpu)
        if err is not None:
            print("%-16s FAILED\\n%s\\n" % (tag, err))
            results[(model, gpu)] = None
        else:
            rate = CELLS[model] * ITERS[model] / dt
            results[(model, gpu)] = (dt, rate)
            print("%-16s %8.1f s   %7.1f M cell-updates/s"
                  % (tag, dt, rate / 1e6))
'''

VERDICT = f'''LOCAL = {{"model_a": {LOCAL_NONDISP}, "model_b": {LOCAL_DISP}}}
LOCAL_BSCAN_S = {LOCAL_BSCAN_S}
MATRIX = {MATRIX_BSCANS}

print("%-10s%12s%12s%12s%14s"
      % ("model", "local", "colab CPU", "colab GPU", "GPU vs local"))
gain = None
for model in ("model_a", "model_b"):
    cpu = results.get((model, False))
    gpu = results.get((model, True))
    lo = LOCAL[model]
    row = "%-10s%11.0fM" % (model, lo / 1e6)
    row += "%11.0fM" % (cpu[1] / 1e6) if cpu else "%12s" % "failed"
    row += "%11.0fM" % (gpu[1] / 1e6) if gpu else "%12s" % "failed"
    row += "%13.2fx" % (gpu[1] / lo) if gpu else "%14s" % "-"
    print(row)
    if model == "model_b" and gpu:
        gain = gpu[1] / lo

print()
if gain is None:
    print("The GPU solver did not run on the production model.")
    print("Keep the matrix on the laptop.")
elif gain > 1.5:
    local_h = MATRIX * LOCAL_BSCAN_S / 3600
    print("GPU is %.1fx the laptop on the production model." % gain)
    print("Full matrix: %.1f h locally -> %.1f h here." % (local_h, local_h / gain))
    print("Worth moving, but in chunks checkpointed to Drive: free sessions")
    print("cap near 12 h and idle out after about 90 minutes.")
else:
    print("GPU is only %.2fx the laptop. Not worth the session-management" % gain)
    print("cost - keep the matrix local.")
'''

NOTES = """## Notes

**Session limits.** Free Colab caps a session near 12 hours and disconnects
after roughly 90 minutes idle. The matrix cannot run in one sitting whatever the
speedup, so it has to be split into chunks that write results to Drive as they
finish, with the driver skipping work already done.

**Rebuild cost.** gprMax is rebuilt from source every session. Caching the built
tree to Drive avoids paying that each time.

**What does not move.** Only the FDTD solve. Geometry, material fitting,
processing, and statistics all stay local, where iteration is fast and there are
no session limits.
"""

cells = [
    md(INTRO),
    md("## 1. Confirm a GPU is attached"),
    code(CHECK_GPU),
    md("## 2. Build gprMax\n\nFrom source, because the Cython extensions must "
       "match this runtime's Python and NumPy."),
    code(BUILD),
    md("## 3. Install pycuda\n\nThis is what enables the `-gpu` flag. If it "
       "fails, the GPU solver is unavailable and the answer is no."),
    code(PYCUDA),
    md("## 4. Write the benchmark models\n\nIdentical to those measured "
       "locally, so the comparison is like for like.\n\n"
       "- **A** non-dispersive, the original throughput benchmark\n"
       "- **B** the production model with six two-pole Debye tissues, which is "
       "what the matrix actually runs. Dispersion costs 2.4x locally, and the "
       "CUDA kernels do handle multi-pole dispersive materials, so B is the "
       "number that decides this."),
    code(WRITE_MODELS),
    md("## 5. Run each model on CPU and GPU\n\nExpect poor CPU numbers - two "
       "vCPUs. They are recorded only to show the GPU speedup is real rather "
       "than an artefact of the runtime."),
    code(RUN),
    md("## 6. Verdict"),
    code(VERDICT),
    md(NOTES),
]

nb = {
    "nbformat": 4,
    "nbformat_minor": 0,
    "metadata": {
        "colab": {"provenance": [], "gpuType": "T4"},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
        "accelerator": "GPU",
    },
    "cells": cells,
}

out = (Path(__file__).resolve().parent.parent / "notebooks"
       / "colab_gpu_benchmark.ipynb")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(nb, indent=1))
print("wrote %s (%d cells)" % (out, len(cells)))
