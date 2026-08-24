"""Why does the no-rod control still score 51 dB?

Stage 4 cleared its gate but left this open: with k=1 the target-free control
image is not at the noise floor, so the detector has a dirty reference and any
ROC analysis built on it inherits that. Section 5 of the proposal makes AUC the
primary endpoint, so this has to be understood before Stage 7.

The suspicion was that the phantom tank has two flat interfaces - its surface
and its floor at 36 mm - and that one discarded singular component cannot
remove both. This checks that directly by asking what each component actually
contains, rather than assuming.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.detect.metrics import detect_snr
from bonesim.forward.base import ScanData
from bonesim.perturb.errors import Instrument
from bonesim.process.clutter import remove_clutter_svd, subtract_empty_scene
from bonesim.process.migrate import migrate

RUNS = Path(__file__).resolve().parent.parent / "runs"
ROD_X, ROD_Z, TANK = 0.050, 0.020, 0.036
Z_WINDOW = (0.005, 0.035)


def prep(tag):
    d = ScanData.load(RUNS / f"stage4_{tag}.npz")
    ref = ScanData(d.f, d.x, np.ones_like(d.s11), d.z_antenna, {})
    return Instrument().apply_post(subtract_empty_scene(d, ref))


def main() -> int:
    rod, norod = prep("rod20"), prep("norod")

    print("=" * 74)
    print("1. Singular spectra")
    print("=" * 74)
    s_rod = np.linalg.svd(rod.s11, compute_uv=False)
    s_non = np.linalg.svd(norod.s11, compute_uv=False)
    print(f"  {'i':>3}{'rod s_i/s_0':>14}{'no-rod s_i/s_0':>16}{'ratio':>10}")
    for i in range(7):
        print(f"  {i:>3}{s_rod[i]/s_rod[0]:>14.3e}{s_non[i]/s_non[0]:>16.3e}"
              f"{s_rod[i]/s_non[i]:>10.2f}")
    print("\n  A component holding the rod should stand out in the ratio.")

    print()
    print("=" * 74)
    print("2. Where does each component put its energy in the image?")
    print("=" * 74)
    u, sv, vh = np.linalg.svd(rod.s11, full_matrices=False)
    print(f"  {'component':>10}{'peak x mm':>12}{'peak z mm':>12}"
          f"{'lateral spread':>16}   interpretation")
    for i in range(5):
        only = rod.copy_with(sv[i] * np.outer(u[:, i], vh[i]))
        img = migrate(only, 20.0)
        env = img.envelope
        rows = (img.z >= Z_WINDOW[0]) & (img.z <= Z_WINDOW[1])
        sub = env[rows]
        iz, ix = np.unravel_index(int(np.argmax(sub)), sub.shape)
        # A flat interface is laterally uniform; a rod is localised.
        prof = sub.max(axis=0)
        spread = float((prof > 0.5 * prof.max()).sum() * (img.x[1] - img.x[0]))
        near_rod = abs(img.x[ix] - ROD_X) < 0.004
        tag = ("localised, at the rod" if near_rod and spread < 0.02
               else "laterally extended (flat interface)" if spread > 0.03
               else "mixed")
        print(f"  {i:>10}{img.x[ix]*1e3:>12.1f}{img.z[rows][iz]*1e3:>12.1f}"
              f"{spread*1e3:>13.0f} mm   {tag}")

    print()
    print("=" * 74)
    print("3. Detector score against k, rod and control")
    print("=" * 74)
    print(f"  {'k':>3}{'rod SNR':>10}{'control SNR':>13}{'separation':>12}"
          f"{'rod x mm':>10}{'x err':>8}")
    best = None
    for k in range(0, 6):
        try:
            r = remove_clutter_svd(rod, k=k)
            n = remove_clutter_svd(norod, k=k)
        except ValueError:
            continue
        dr = detect_snr(migrate(r, 20.0), r, z_window=Z_WINDOW)
        dn = detect_snr(migrate(n, 20.0), n, z_window=Z_WINDOW)
        sep = dr.ratio_db - dn.ratio_db
        err = abs(dr.x_peak - ROD_X) * 1e3
        print(f"  {k:>3}{dr.ratio_db:>10.1f}{dn.ratio_db:>13.1f}{sep:>12.1f}"
              f"{dr.x_peak*1e3:>10.1f}{err:>8.1f}")
        if err < 3.0 and (best is None or sep > best[1]):
            best = (k, sep, dn.ratio_db)

    print()
    if best:
        k, sep, ctrl = best
        print(f"best k with correct localisation: {k}, separation {sep:.1f} dB, "
              f"control at {ctrl:.1f} dB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
