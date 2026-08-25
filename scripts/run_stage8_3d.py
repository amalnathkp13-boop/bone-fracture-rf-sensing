"""Stage 8: does the result survive in three dimensions?

Every result in this project so far comes from a 2D TMz plane, and "two
dimensional propagation" has been listed as a limitation throughout. This
stage removes it, on a reduced scale, by solving the same detection problem on
a genuinely cylindrical limb.

What changes, and why it is not obvious which way the answer goes:

  - **Curvature defocuses.** A cylindrical skin surface spreads the reflected
    wavefront transversely; a flat one does not. Costs signal.
  - **Energy leaves the plane.** 2D traps in-plane what 3D lets escape.
    Costs signal.
  - **The crack is longer than the plane suggests.** A transverse fracture
    severs a curved cortical wall, so the scattering edge is an arc rather
    than a point, illuminated over a range of incidence angles. Returns
    signal the flat model cannot.

The fair-comparison problem. A 3D grid fine enough for 11 GHz is
unaffordable, so the 3D band is roughly 2-6 GHz. Comparing that against a 2D
result computed over 3-11 GHz would confound geometry with bandwidth - and the
bandwidth study already showed bandwidth is worth 22.9 dB here, which is far
larger than any plausible geometric effect. **Both models are therefore scored
over the same 3.0-6.0 GHz window.**

    python scripts/run_stage8_3d.py --decks     # write the input files
    python scripts/run_stage8_3d.py --analyse   # score whatever has been solved
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.detect.metrics import detect_snr
from bonesim.forward.base import ScanData
from bonesim.forward.gprmax import assemble, sorted_outputs
from bonesim.forward.gprmax3d import GridSpec3D, build_input, estimate
from bonesim.geometry.cylindrical import CylindricalPhantom
from bonesim.geometry.phantom import Fracture
from bonesim.perturb.errors import Instrument
from bonesim.process.clutter import remove_clutter_selective, subtract_empty_scene
from bonesim.process.migrate import migrate

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "runs" / "stage8_3d"
MATERIALS = ROOT / "config" / "materials.in"

# The band both models are scored over. Set by what 3D can afford, not by
# preference, and applied to the 2D data as well so the comparison is fair.
BAND = (3.0e9, 6.0e9)
F_OUT = np.linspace(*BAND, 121)

X0, N_POS, STEP = 0.020, 21, 0.0025      # 20 to 70 mm along the bone
EPS_AVG = 26.0
Z_WINDOW = (0.003, 0.024)
X_MARGIN = 0.010

SCENES = [
    ("intact", None),
    ("kerf10", Fracture(0.045, 0.001)),
    ("kerf20", Fracture(0.045, 0.002)),
]


def write_decks() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    grid = GridSpec3D()
    base = CylindricalPhantom(length=grid.length)
    grid.check(base)

    n_models = 0
    for name, fr in SCENES:
        ph = base.with_fracture(fr)
        deck = build_input(ph, grid, MATERIALS, X0, N_POS, STEP,
                           title=f"3D cylindrical limb, {name}")
        (WORK / f"{name}.in").write_text(deck, encoding="utf-8", newline="\n")
        n_models += N_POS
    ref = build_input(None, grid, MATERIALS, X0, 1, 0.0,
                      title="3D free-space reference")
    (WORK / "reference.in").write_text(ref, encoding="utf-8", newline="\n")
    n_models += 1

    e = estimate(grid, n_models)
    print(f"  wrote {len(SCENES) + 1} decks to {WORK}")
    print(f"  {base.summary()}")
    print(f"  grid {grid.dx*1e3:.1f} mm, {grid.cells/1e6:.1f} M cells, "
          f"{e['timesteps']} timesteps")
    print(f"  {n_models} models -> about {e['hours']:.2f} h on a Colab T4")
    print()
    print("  Run each with:  python -m gprMax <name>.in -n "
          f"{N_POS} -gpu    (reference uses -n 1)")


def load(name: str) -> ScanData:
    x = X0 + np.arange(N_POS) * STEP
    return assemble(WORK, [name], "reference", F_OUT, x,
                    z_antenna=-CylindricalPhantom().standoff,
                    meta={"model": "gprmax3d", "scene": name})


def score(d: ScanData, repeat: int = 0) -> float:
    ref = ScanData(d.f, d.x, np.ones_like(d.s11), d.z_antenna, {})
    inst = Instrument(seed=repeat)
    clean = remove_clutter_selective(
        inst.apply_post(subtract_empty_scene(d, ref)), EPS_AVG)[0]
    det = detect_snr(migrate(clean, EPS_AVG), clean,
                     z_window=Z_WINDOW, x_margin=X_MARGIN)
    return det.ratio_db


def analyse() -> None:
    if not (WORK / "reference1.out").exists() and \
            not list(WORK.glob("reference*.out")):
        print("  no solved output in", WORK)
        print("  write the decks, solve them, then re-run with --analyse")
        return

    print("=" * 72)
    print(f"Stage 8: 3D cylindrical limb, scored over "
          f"{BAND[0]/1e9:.1f}-{BAND[1]/1e9:.1f} GHz")
    print("=" * 72)
    rows = []
    for name, fr in SCENES:
        if not list(WORK.glob(f"{name}*.out")):
            print(f"  {name}: not solved yet")
            continue
        d = load(name)
        s = [score(d, r) for r in range(3)]
        rows.append((name, float(np.mean(s)), float(np.std(s))))
        print(f"  {name:<10} {np.mean(s):7.1f} dB   (sd {np.std(s):.2f} "
              f"over 3 error realisations)")

    if len(rows) < 2:
        return
    intact = next((r for r in rows if r[0] == "intact"), None)
    if intact is None:
        return
    print()
    print(f"  {'scene':<10}{'margin over intact':>22}")
    for name, m, _ in rows:
        if name == "intact":
            continue
        print(f"  {name:<10}{m - intact[1]:>19.1f} dB")
    print()
    print("  Compare against the same 2D cells scored over the same band:")
    print("    python scripts/run_band_study.py 3.0 6.0 '3D comparison band'")


if __name__ == "__main__":
    if "--analyse" in sys.argv:
        analyse()
    elif "--decks" in sys.argv:
        write_decks()
    else:
        print(__doc__)
