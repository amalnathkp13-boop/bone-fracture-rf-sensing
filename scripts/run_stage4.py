"""Stage 4: the brass-rod gate (proposal section 9).

    "Verify with a known strong scatterer first: if you cannot image a 6 mm
    brass rod at 20 mm depth in phantom, you will never image a fracture."

A 6 mm PEC rod in a uniform muscle-equivalent phantom, scanned and reconstructed
by exactly the same code as the fracture study. Because the rod is a far
stronger and simpler target, failure here would locate the fault in the
processing chain rather than in the physics of fracture detection.

Three things are checked, in increasing strictness:

  1. the rod is found, laterally, to better than 3 mm
  2. its depth is recovered to better than 5 mm, which the fracture study could
     not manage and which a strong isolated target should make possible
  3. the detector separates rod from no-rod by a wide margin

Also sweeps rod depth, since the proposal's claimed working range is 15-20 mm
from the skin surface (section 2.7) and this is the cheapest way to test it.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.detect.metrics import detect_snr
from bonesim.forward.base import ScanData
from bonesim.forward.bscan import BScanPlan, run_bscan
from bonesim.forward.gprmax import GridSpec
from bonesim.geometry.validation import RodPhantom
from bonesim.perturb.errors import Instrument
from bonesim.process.autofocus import autofocus
from bonesim.process.clutter import remove_clutter_svd, subtract_empty_scene

RUNS = Path(__file__).resolve().parent.parent / "runs"
ROD_X = 0.050

# The phantom tank is deeper than a limb, so the domain and the time window both
# have to grow: 36 mm of phantom leaves 5 mm below a rod at 28 mm, and the round
# trip through 36 mm of muscle-equivalent needs more than the 2.5 ns the limb
# model used. The guards in GridSpec.check refuse anything smaller.
GRID = GridSpec(depth=0.062, time_window=3.0e-9)
TANK = 0.036


def acquire(phantom, tag, plan):
    """Run a B-scan, or reuse the saved one if it is already there."""
    path = RUNS / f"stage4_{tag}.npz"
    if path.exists():
        print(f"  {tag:<14} (cached)          {phantom.describe()}")
        return ScanData.load(path)
    t0 = time.time()
    d = run_bscan(phantom, RUNS / f"stage4_{tag}", plan=plan,
                  grid=GRID, n_proc=4)
    d.save(path)
    print(f"  {tag:<14} {time.time()-t0:6.1f} s   {phantom.describe()}")
    return d


def reconstruct(data, k=1, eps=None):
    inst = Instrument()
    ref = ScanData(data.f, data.x, np.ones_like(data.s11), data.z_antenna, {})
    clean = remove_clutter_svd(
        inst.apply_post(subtract_empty_scene(data, ref)), k=k)
    if eps is None:
        r = autofocus(clean, 4.0, 45.0, n_coarse=21)
        return r.image, clean, r.eps_avg
    from bonesim.process.migrate import migrate
    return migrate(clean, eps), clean, eps


def main() -> int:
    plan = BScanPlan(x_start=0.020, x_stop=0.080, step=0.001)
    RUNS.mkdir(exist_ok=True)

    print("=" * 76)
    print("Acquisition")
    print("=" * 76)
    rod = RodPhantom(depth=TANK)
    scans = {
        "rod20": acquire(rod, "rod20", plan),
        "norod": acquire(rod.without_rod(), "norod", plan),
        "rod12": acquire(RodPhantom(rod_depth=0.012, depth=TANK), "rod12", plan),
        "rod28": acquire(RodPhantom(rod_depth=0.028, depth=TANK), "rod28", plan),
    }

    print()
    print("=" * 76)
    print("1. The gate: a 6 mm rod at 20 mm depth")
    print("=" * 76)
    img, clean, eps = reconstruct(scans["rod20"])
    det = detect_snr(img, clean, z_window=(0.005, 0.035))
    img0, clean0, _ = reconstruct(scans["norod"], eps=eps)
    det0 = detect_snr(img0, clean0, z_window=(0.005, 0.035))

    x_err = abs(det.x_peak - ROD_X) * 1e3
    z_err = abs(det.z_peak - rod.rod_depth) * 1e3
    print(f"  autofocused eps_avg   {eps:.1f}")
    print(f"  rod found at          x = {det.x_peak*1e3:.1f} mm "
          f"(true {ROD_X*1e3:.0f}), z = {det.z_peak*1e3:.1f} mm "
          f"(true {rod.rod_depth*1e3:.0f})")
    print(f"  error                 x {x_err:.1f} mm, z {z_err:.1f} mm")
    print(f"  SNR                   rod {det.ratio_db:.1f} dB, "
          f"no rod {det0.ratio_db:.1f} dB, "
          f"separation {det.ratio_db - det0.ratio_db:.1f} dB")
    print(f"  peak amplitude        rod {img.envelope.max():.3e}, "
          f"no rod {img0.envelope.max():.3e} "
          f"({img.envelope.max()/img0.envelope.max():.0f}x)")

    print()
    print("=" * 76)
    print("2. Sensitivity to k")
    print("=" * 76)
    print(f"  {'k':>3}{'x mm':>9}{'x err':>8}{'z mm':>9}{'z err':>8}{'SNR dB':>9}")
    for k in (1, 2, 3):
        im, cl, _ = reconstruct(scans["rod20"], k=k, eps=eps)
        d = detect_snr(im, cl, z_window=(0.005, 0.035))
        print(f"  {k:>3}{d.x_peak*1e3:>9.1f}{abs(d.x_peak-ROD_X)*1e3:>8.1f}"
              f"{d.z_peak*1e3:>9.1f}{abs(d.z_peak-rod.rod_depth)*1e3:>8.1f}"
              f"{d.ratio_db:>9.1f}")

    print()
    print("=" * 76)
    print("3. Depth sweep (proposal 2.7 claims 15-20 mm working range)")
    print("=" * 76)
    print(f"  {'true z':>8}{'found z':>10}{'z err':>8}{'x err':>8}"
          f"{'SNR dB':>9}{'eps_avg':>9}")
    for tag, z_true in (("rod12", 0.012), ("rod20", 0.020), ("rod28", 0.028)):
        im, cl, e = reconstruct(scans[tag])
        d = detect_snr(im, cl, z_window=(0.005, 0.035))
        print(f"  {z_true*1e3:>7.0f} {d.z_peak*1e3:>9.1f}"
              f"{abs(d.z_peak-z_true)*1e3:>8.1f}"
              f"{abs(d.x_peak-ROD_X)*1e3:>8.1f}{d.ratio_db:>9.1f}{e:>9.1f}")

    print()
    ok = x_err < 3.0 and z_err < 5.0 and (det.ratio_db - det0.ratio_db) > 10.0
    if ok:
        print("STAGE 4 PASS - the chain images a known strong scatterer.")
        print("The week-6 go/no-go of proposal section 9 is cleared.")
    else:
        print("STAGE 4 FAIL - debug in the order the proposal gives:")
        print("  calibration, empty-scene subtraction, eps_avg, then geometry.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
