"""Why does autofocus rail against its upper bound?

Stage 3 reported eps_avg = 20.0, the top of a 4-20 search, with entropy flat to
within 2% over 14.0-20.0. Three possibilities, tested here:

  1. the true optimum lies above 20 and the range is simply too narrow
  2. entropy is the wrong focus metric for this data
  3. there is no sharp optimum at all, and the depth estimate is therefore
     weakly determined whatever metric is used

Also re-checks the reported depth error against the right reference. A
transverse fracture is a blood-filled gap spanning the whole cortical wall, from
z_cortex to z_cortex + cortex, so its scattering centroid is mid-wall - not the
cortex surface the first pass compared against.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.forward.base import ScanData
from bonesim.geometry.phantom import Fracture, Phantom
from bonesim.perturb.errors import Instrument
from bonesim.process.clutter import remove_clutter_svd, subtract_empty_scene
from bonesim.process.migrate import migrate

RUNS = Path(__file__).resolve().parent.parent / "runs"
X_FRAC = 0.050


def main() -> int:
    ph = Phantom().with_fracture(Fracture(X_FRAC, 0.001))
    z_top = ph.z_cortex
    z_bot = ph.z_cortex + ph.cortex
    z_mid = 0.5 * (z_top + z_bot)
    print(f"fracture gap spans z = {z_top*1e3:.1f} to {z_bot*1e3:.1f} mm, "
          f"centroid {z_mid*1e3:.1f} mm")
    print("the first pass wrongly compared against the cortex surface alone\n")

    # Expected effective permittivity of the tissue path down to the centroid.
    from bonesim.materials import tissues as T
    f0 = 7e9
    opt, phys = 0.0, 0.0
    for mat, a, b in ph.stack():
        if a >= z_mid:
            break
        seg = min(b, z_mid) - a
        n = float(np.sqrt(T.get(mat).eps_real(f0)))
        opt += seg * n
        phys += seg
    eps_expect = (opt / phys) ** 2
    print(f"expected eps_avg from the layer stack at 7 GHz: {eps_expect:.1f}\n")

    fr = ScanData.load(RUNS / "stage3_fractured.npz")
    ref = ScanData(fr.f, fr.x, np.ones_like(fr.s11), fr.z_antenna, {})
    clean = remove_clutter_svd(
        Instrument().apply_post(subtract_empty_scene(fr, ref)), k=1)

    grid = np.concatenate([np.arange(4.0, 24.0, 2.0), np.arange(24.0, 61.0, 4.0)])
    print(f"{'eps_avg':>8}{'entropy':>11}{'peak/avg':>11}{'peak x mm':>11}"
          f"{'peak z mm':>11}{'x err':>8}")
    rows = []
    for e in grid:
        img = migrate(clean, float(e))
        env = img.envelope
        iz, ix = np.unravel_index(int(np.argmax(env)), env.shape)
        ent, pa = img.entropy(), img.peak_to_average()
        rows.append((e, ent, pa, img.x[ix], img.z[iz]))
        print(f"{e:>8.0f}{ent:>11.4f}{pa:>11.2f}{img.x[ix]*1e3:>11.1f}"
              f"{img.z[iz]*1e3:>11.1f}{abs(img.x[ix]-X_FRAC)*1e3:>8.1f}")

    eps, ent, pa, xs, zs = map(np.array, zip(*rows))
    i_ent, i_pa = int(np.argmin(ent)), int(np.argmax(pa))
    print()
    print(f"entropy minimum        at eps_avg = {eps[i_ent]:.0f}  "
          f"-> z = {zs[i_ent]*1e3:.1f} mm")
    print(f"peak-to-average maximum at eps_avg = {eps[i_pa]:.0f}  "
          f"-> z = {zs[i_pa]*1e3:.1f} mm")
    spread = (ent.max() - ent.min()) / abs(ent.min())
    print(f"entropy varies by only {spread:.2%} across eps_avg 4-60")

    inside = (zs >= z_top) & (zs <= z_bot)
    print(f"\ndepth lands inside the gap for {inside.sum()}/{len(zs)} "
          f"values of eps_avg")
    good_x = np.abs(xs - X_FRAC) < 0.003
    print(f"lateral position within 3 mm for {good_x.sum()}/{len(xs)} "
          f"values of eps_avg")
    print("\nlateral localisation is set by aperture geometry, not by the")
    print("assumed velocity, which is why it survives a bad eps_avg.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
