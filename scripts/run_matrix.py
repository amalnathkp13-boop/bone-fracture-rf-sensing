"""Stage 6: solve the experiment matrix, resumably.

192 B-scans (see bonesim/experiment.py). Measured at 14 min per cell on this
laptop, so about 45 h here or 6.3 h on a Colab T4 - the GPU is 7.18x faster on
the production model (docs/colab.md).

That is longer than the 32.5 h projected in Stage 3, because the matrix needs a
60 mm domain rather than 55 mm: specimen variation can draw a 12 mm overlay on
a 5.2 mm cortical wall, and the domain has to clear the deepest specimen the
design can produce, not the nominal one.

Resumability is not a convenience here. A B-scan is ten minutes, the whole
matrix is many hours, and both places it can run will interrupt it: a laptop
suspends, and a free Colab session is reclaimed without warning. Stage 4 already
lost a completed 62-model scan to a driver timeout that fired while the machine
slept, with every output file intact on disk.

So the unit of work is one cell, one file. Anything already on disk is skipped,
at two levels: the assembled .npz here, and the individual gprMax outputs inside
run_bscan. Interrupt it at any point and rerun; it continues.

Usage
    python scripts/run_matrix.py                      # everything outstanding
    python scripts/run_matrix.py --limit 5            # a few, to check timing
    python scripts/run_matrix.py --out /content/drive/MyDrive/bonesim
    python scripts/run_matrix.py --dry-run            # plan only, solve nothing
"""
from __future__ import annotations

import argparse
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.experiment import build_matrix, matrix_summary
from bonesim.forward.bscan import BScanPlan, run_bscan
from bonesim.forward.gprmax import GridSpec

# Sized for the deepest specimen the matrix can draw: 30.4 mm of anatomy under
# a 12 mm standoff, plus a margin at each end. GridSpec.check refuses anything
# shallower, so this is verified rather than assumed.
GRID = GridSpec(depth=0.060, time_window=2.5e-9)
PLAN = BScanPlan(x_start=0.020, x_stop=0.080, step=0.001)


def human(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds/60:.0f}m"
    return f"{seconds/3600:.1f}h"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None,
                    help="directory for the .npz files (default runs/matrix)")
    ap.add_argument("--scratch", default=None,
                    help="directory for gprMax working files")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after this many newly solved cells")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--gpu", action="store_true",
                    help="pass -gpu to gprMax (NVIDIA only)")
    ap.add_argument("--n-proc", type=int, default=4)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    out = Path(args.out) if args.out else root / "runs" / "matrix"
    out.mkdir(parents=True, exist_ok=True)

    on_windows = platform.system() == "Windows"
    scratch = Path(args.scratch) if args.scratch else (
        Path("/root/bonesim-runs/matrix") if not on_windows
        else out / "_work")
    scratch.mkdir(parents=True, exist_ok=True)

    cells = build_matrix()
    for c in cells:
        GRID.check(c.phantom)          # fail before solving, not during

    done = [c for c in cells if (out / f"{c.key}.npz").exists()]
    todo = [c for c in cells if not (out / f"{c.key}.npz").exists()]

    print(matrix_summary(cells))
    print()
    print(f"output   {out}")
    print(f"scratch  {scratch}")
    print(f"complete {len(done)}/{len(cells)}    outstanding {len(todo)}")
    if args.limit:
        todo = todo[:args.limit]
        print(f"limit    solving {len(todo)} this run")
    if args.dry_run:
        print("\ndry run: nothing solved")
        for c in todo[:8]:
            print(f"  would solve {c.key}  ({c.describe()})")
        if len(todo) > 8:
            print(f"  ... and {len(todo)-8} more")
        return 0
    if not todo:
        print("\nmatrix complete")
        return 0

    print()
    times: list[float] = []
    for i, c in enumerate(todo, 1):
        t0 = time.time()
        try:
            d = run_bscan(c.phantom, scratch / c.key, plan=PLAN, grid=GRID,
                          n_proc=1 if args.gpu else args.n_proc,
                          threads=args.threads, gpu=args.gpu,
                          wsl_distro="Ubuntu" if on_windows else None)
        except Exception as exc:                       # noqa: BLE001
            # One bad cell must not abandon the run; it will be retried on the
            # next invocation because its .npz was never written.
            print(f"  [{i}/{len(todo)}] {c.key}  FAILED: {exc}")
            continue
        d.meta.update(specimen=c.specimen, state=c.state, overlay=c.overlay,
                      kerf=c.kerf, fractured=c.fractured)
        d.save(out / f"{c.key}.npz")
        dt = time.time() - t0
        times.append(dt)
        eta = np.median(times) * (len(todo) - i)
        print(f"  [{i}/{len(todo)}] {c.key}  {human(dt)}"
              f"   median {human(float(np.median(times)))}"
              f"   eta {human(eta)}")

    remaining = sum(1 for c in cells if not (out / f"{c.key}.npz").exists())
    print(f"\n{len(cells)-remaining}/{len(cells)} complete, "
          f"{remaining} outstanding")
    return 0


if __name__ == "__main__":
    sys.exit(main())
