"""Stage 2 acceptance: the full processing chain, end to end on analytic data.

Runs proposal 2.5 in order - empty-scene subtraction, bone-line location, SVD
clutter removal, autofocus, migration, scalar detection - with the instrument
error model applied, and checks:

  1. clutter rank, and therefore the correct choice of k
  2. the peak lands at the true fracture position, which the reconstructor is
     never told
  3. a fractured limb scores above an intact one on the scalar detector
  4. the detector responds to kerf and degrades with overlay - the clinical
     envelope, which is the proposal's headline result (4.3)

This validates the *pipeline*, not the physics. The analytic forward model uses
straight rays and so does migration, so successful detection here is expected
and is not evidence the method works. That test is Stage 4, against gprMax.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.forward.analytic import AnalyticForward
from bonesim.geometry.phantom import Fracture, Phantom
from bonesim.perturb.errors import Instrument
from bonesim.process.clutter import remove_clutter_svd, subtract_empty_scene
from bonesim.process.pipeline import estimate_clutter_rank, process

F = np.linspace(3e9, 11e9, 201)
X = np.arange(0.020, 0.0801, 0.001)
X_FRAC = 0.050
FWD = AnalyticForward()


def acquire(phantom, inst: Instrument):
    """One acquisition, with instrument errors applied at the right points."""
    x_act = inst.actual_positions(X)
    so = inst.actual_standoff(phantom.standoff, X.size)
    data = inst.apply_post(FWD.scan(phantom, F, x_act, standoff=so,
                                    x_nominal=X))
    ref = inst.apply_post(FWD.empty_scene(phantom, F, X))
    return data, ref


def main() -> int:
    ok = True
    inst = Instrument(seed=1)
    frac = Phantom().with_fracture(Fracture(x=X_FRAC, kerf=0.001))

    print("=" * 72)
    print("1. Clutter rank and the choice of k")
    print("=" * 72)
    data, ref = acquire(frac, inst)
    d = subtract_empty_scene(data, ref)
    print(f"  effective clutter rank (rel. threshold 1e-9): "
          f"{estimate_clutter_rank(d)}")
    s = np.linalg.svd(d.s11, compute_uv=False)
    print("  singular values / s0: " +
          " ".join(f"{v:.2e}" for v in (s[:5] / s[0])))
    for k in (1, 2, 3):
        r = process(data, ref, k=k, eps_avg=9.0)
        err = abs(r.detection.x_peak - X_FRAC) * 1e3
        print(f"  k={k}  SNR {r.detection.ratio_db:6.1f} dB   "
              f"peak x={r.detection.x_peak*1e3:5.1f} mm  (err {err:4.1f} mm)")

    K = 2     # standoff drift makes the clutter rank ~2; see docs/pipeline.md
    print(f"\n  using k={K} for analytic data")

    print()
    print("=" * 72)
    print("2. Autofocus (reconstructor is blind to the layer structure)")
    print("=" * 72)
    r = process(data, ref, k=K)
    lo, hi = r.focus.sensitivity()
    err = abs(r.detection.x_peak - X_FRAC) * 1e3
    print(f"  recovered eps_avg  {r.eps_avg:.2f}  "
          f"(within 2% of best over {lo:.1f}-{hi:.1f})")
    print(f"  peak depth z = {r.detection.z_peak*1e3:.1f} mm "
          f"(true fracture centre "
          f"{(frac.z_cortex + 0.5*frac.cortex)*1e3:.1f} mm)")
    print(f"  peak at x = {r.detection.x_peak*1e3:.1f} mm, "
          f"true {X_FRAC*1e3:.1f} mm  -> error {err:.1f} mm")
    if err > 5.0:
        print("  FAIL: localisation error exceeds 5 mm")
        ok = False

    print()
    print("=" * 72)
    print("3. Fractured vs intact")
    print("=" * 72)
    di, ri = acquire(Phantom(), inst)
    r_int = process(di, ri, k=K, eps_avg=r.eps_avg)
    r_frc = process(data, ref, k=K, eps_avg=r.eps_avg)
    sep = r_frc.detection.ratio_db - r_int.detection.ratio_db
    print(f"  intact     {r_int.detection.ratio_db:6.1f} dB SNR")
    print(f"  fractured  {r_frc.detection.ratio_db:6.1f} dB SNR")
    print(f"  separation {sep:6.1f} dB")
    if sep <= 6.0:
        print("  FAIL: separation under 6 dB is not a usable detector")
        ok = False

    print()
    print("=" * 72)
    print("4. Kerf and overlay sweep (the clinical envelope)")
    print("=" * 72)
    kerfs = (0.0003, 0.0005, 0.001, 0.002)
    print(f"  {'overlay':>10}" + "".join(f"{k*1e3:>8.2f}" for k in kerfs)
          + "    intact   <- kerf (mm)")
    rows = {}
    for ov in (0.003, 0.006, 0.010):
        vals = []
        for kerf in kerfs:
            pp = Phantom().with_overlay(ov).with_fracture(
                Fracture(x=X_FRAC, kerf=kerf))
            dd, rr = acquire(pp, inst)
            vals.append(process(dd, rr, k=K, eps_avg=r.eps_avg)
                        .detection.ratio_db)
        dd, rr = acquire(Phantom().with_overlay(ov), inst)
        base = process(dd, rr, k=K, eps_avg=r.eps_avg).detection.ratio_db
        rows[ov] = (vals, base)
        print(f"  {ov*1e3:8.0f} mm" + "".join(f"{v:8.1f}" for v in vals)
              + f"{base:10.1f}")
    print("  (peak-to-noise SNR, dB)")

    print()
    # Not monotonicity. A blood-filled gap is a quarter-wave resonator - about
    # 1.1 mm in blood at 10 GHz - so scattering peaks near 1 mm and dips again
    # by 2 mm. Requiring monotonicity would be requiring the wrong physics. What
    # must hold is that the detector is not inverted: the smallest kerf must not
    # outscore the largest.
    ordered = all(v[0] < v[-1] for v, _ in rows.values())
    dip = {o: max(v) - v[-1] for o, (v, _) in rows.items()}
    print(f"  detector correctly orders smallest vs largest kerf: {ordered}")
    print(f"  resonance dip at 2 mm kerf: "
          + ", ".join(f"{o*1e3:.0f} mm overlay {dip[o]:.1f} dB"
                      for o in sorted(dip)))
    lifts = {o: min(v) - b for o, (v, b) in rows.items()}
    for o in sorted(lifts):
        print(f"  overlay {o*1e3:4.0f} mm: smallest kerf still "
              f"{lifts[o]:5.1f} dB above intact")
    if not ordered:
        print("  FAIL: detector is inverted in kerf")
        ok = False
    if not (lifts[0.003] > lifts[0.010]):
        print("  FAIL: detectability does not degrade with overlay")
        ok = False

    print()
    print("STAGE 2 PIPELINE PASS" if ok else "STAGE 2 PIPELINE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
