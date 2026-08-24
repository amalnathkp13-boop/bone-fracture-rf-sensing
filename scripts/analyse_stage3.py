"""Re-analyse the Stage 3 B-scans properly.

The first pass reported a peak-to-noise ratio near 300 dB, which is not a
result but an artefact: FDTD output is deterministic, so the estimated receiver
noise came out at machine epsilon and the detector divided by it. It also fixed
eps_avg at 9.0 by hand instead of autofocusing, which put the reconstructed
depth 7 mm below the true cortex.

Both are fixed here:

  * the instrument error model is applied to the solver output, giving the
    detector a real floor to stand on
  * eps_avg is recovered by autofocus, blind, as it must be in practice

No new FDTD is needed - this reads the saved scans.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.forward.base import ScanData
from bonesim.perturb.errors import Instrument
from bonesim.process.autofocus import autofocus
from bonesim.process.clutter import remove_clutter_svd, subtract_empty_scene
from bonesim.process.migrate import migrate
from bonesim.detect.metrics import detect_snr, estimate_sample_noise

RUNS = Path(__file__).resolve().parent.parent / "runs"
X_FRAC, Z_CORTEX = 0.050, 0.006


def main() -> int:
    fr = ScanData.load(RUNS / "stage3_fractured.npz")
    it = ScanData.load(RUNS / "stage3_intact.npz")
    ref = ScanData(fr.f, fr.x, np.ones_like(fr.s11), fr.z_antenna, {})
    inst = Instrument()

    print("=" * 74)
    print("1. Does the noise model give the detector a real floor?")
    print("=" * 74)
    raw = subtract_empty_scene(fr, ref)
    noisy = inst.apply_post(subtract_empty_scene(fr, ref))
    print(f"  {'':22}{'sigma':>12}{'vs signal peak':>18}")
    for name, d in (("noiseless (broken)", raw), ("with instrument", noisy)):
        s = estimate_sample_noise(d)
        print(f"  {name:<22}{s:12.3e}{s/np.abs(d.s11).max():>18.3e}")
    print("  machine epsilon is 2.2e-16; anything near it is not a noise floor")

    print()
    print("=" * 74)
    print("2. Autofocus (eps_avg recovered blind, not fixed by hand)")
    print("=" * 74)
    results = {}
    for name, d in (("fractured", fr), ("intact", it)):
        clean = remove_clutter_svd(inst.apply_post(
            subtract_empty_scene(d, ref)), k=1)
        r = autofocus(clean, 4.0, 20.0, n_coarse=17)
        lo, hi = r.sensitivity()
        det = detect_snr(r.image, clean)
        results[name] = (r, det, clean)
        print(f"  {name:<10} eps_avg {r.eps_avg:5.2f} "
              f"(flat within 2% over {lo:.1f}-{hi:.1f})   "
              f"peak x {det.x_peak*1e3:5.1f} mm  z {det.z_peak*1e3:5.1f} mm  "
              f"SNR {det.ratio_db:5.1f} dB")
    print(f"  true fracture x = {X_FRAC*1e3:.1f} mm, "
          f"cortex surface z = {Z_CORTEX*1e3:.1f} mm")

    print()
    print("=" * 74)
    print("3. Sensitivity to k, at the autofocused eps_avg")
    print("=" * 74)
    eps = results["fractured"][0].eps_avg
    print(f"  {'k':>3}{'frac x mm':>11}{'err mm':>9}{'frac SNR':>11}"
          f"{'intact SNR':>12}{'separation':>12}")
    for k in (1, 2, 3, 4):
        row = {}
        for name, d in (("fractured", fr), ("intact", it)):
            clean = remove_clutter_svd(inst.apply_post(
                subtract_empty_scene(d, ref)), k=k)
            row[name] = detect_snr(migrate(clean, eps), clean)
        err = abs(row["fractured"].x_peak - X_FRAC) * 1e3
        sep = row["fractured"].ratio_db - row["intact"].ratio_db
        flag = "" if err < 3.0 else "   <- mislocalised"
        print(f"  {k:>3}{row['fractured'].x_peak*1e3:>11.1f}{err:>9.1f}"
              f"{row['fractured'].ratio_db:>11.1f}"
              f"{row['intact'].ratio_db:>12.1f}{sep:>12.1f}{flag}")

    print()
    print("=" * 74)
    print("4. Does the detector respond to target strength?")
    print("=" * 74)
    print("  (a ratio detector that ignores kerf is not a detector)")
    r, det, clean = results["fractured"]
    print(f"  fractured peak amplitude {r.image.envelope.max():.3e}")
    ri, deti, cleani = results["intact"]
    print(f"  intact    peak amplitude {ri.image.envelope.max():.3e}")
    print(f"  ratio {r.image.envelope.max()/ri.image.envelope.max():.1f}x")
    return 0


if __name__ == "__main__":
    sys.exit(main())
