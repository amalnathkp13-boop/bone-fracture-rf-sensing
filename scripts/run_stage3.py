"""Stage 3 acceptance: a full gprMax B-scan through the unchanged pipeline.

This is the first result in the project that is not an inverse crime. The
analytic model of Stage 2 used straight rays and so does migration, so
detection there was guaranteed by construction. Here the data comes from a
full-wave solver with dispersive layered tissue, a curved wavefront, near-field
antenna coupling and multiple reflections, and the reconstructor still knows
only a single scalar permittivity.

Runs a fractured and an intact limb, pushes both through the same code the
analytic study used, and reports whether the fracture is found.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.forward.bscan import BScanPlan, run_bscan, run_empty_scene
from bonesim.geometry.phantom import Fracture, Phantom
from bonesim.process.pipeline import process

RUNS = Path(__file__).resolve().parent.parent / "runs"
X_FRAC = 0.050


def main() -> int:
    plan = BScanPlan(x_start=0.020, x_stop=0.080, step=0.001)
    print(f"{plan.x.size} positions, {plan.step*1e3:g} mm steps, "
          f"{plan.f[0]/1e9:g}-{plan.f[-1]/1e9:g} GHz\n")

    cases = {
        "fractured": Phantom().with_fracture(Fracture(X_FRAC, 0.001)),
        "intact": Phantom(),
    }
    data = {}
    for name, ph in cases.items():
        t0 = time.time()
        d = run_bscan(ph, RUNS / f"stage3_{name}", plan=plan, n_proc=4)
        d.save(RUNS / f"stage3_{name}.npz")
        data[name] = d
        print(f"  {name:<10} {time.time()-t0:6.1f} s   {ph.describe()}")

    ref = run_empty_scene(RUNS, plan=plan)

    print()
    print("=" * 70)
    print("Raw contrast (before any processing)")
    print("=" * 70)
    df = data["fractured"].s11
    di = data["intact"].s11
    clut = np.abs(di - 1.0).max()
    sig = np.abs(df - di).max()
    print(f"  skin reflection      {clut:.4e}")
    print(f"  fracture response    {sig:.4e}   "
          f"({20*np.log10(sig/clut):.1f} dB below clutter)")

    print()
    print("=" * 70)
    print("Through the pipeline (reconstructor blind to all geometry)")
    print("=" * 70)
    print(f"  {'case':<12}{'k':>3}{'SNR dB':>10}{'peak x mm':>12}"
          f"{'peak z mm':>12}{'err mm':>9}")
    best = None
    for k in (1, 2, 3):
        row = {}
        for name in cases:
            r = process(data[name], ref, k=k, eps_avg=9.0)
            row[name] = r
            err = (abs(r.detection.x_peak - X_FRAC) * 1e3
                   if name == "fractured" else float("nan"))
            print(f"  {name:<12}{k:>3}{r.detection.ratio_db:>10.1f}"
                  f"{r.detection.x_peak*1e3:>12.1f}"
                  f"{r.detection.z_peak*1e3:>12.1f}{err:>9.1f}")
        sep = (row["fractured"].detection.ratio_db
               - row["intact"].detection.ratio_db)
        err = abs(row["fractured"].detection.x_peak - X_FRAC) * 1e3
        print(f"  {'':12}{'':3}{'separation':>10} {sep:5.1f} dB")
        if best is None or (err < 5.0 and sep > best[1]):
            best = (k, sep, err)
        print()

    k, sep, err = best
    print(f"best: k={k}, separation {sep:.1f} dB, localisation error {err:.1f} mm")
    ok = err < 5.0 and sep > 3.0
    print("\nSTAGE 3 PASS" if ok else "\nSTAGE 3 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
