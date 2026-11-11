"""Does a cheap VNA work? Score the solved matrix over each fallback's band.

The proposal's Path A bill of materials offers three VNA options and guesses
at the consequences of the cheap ones:

    LiteVNA-64        50 kHz - 6.3 GHz   "band-limited; degrades resolution"
    NanoVNA V2 Plus4  to 4.4 GHz         "minimum viable, marginal"

Those were guesses because the matrix had not been solved. It has now, and
every cell stores the full 3-11 GHz response, so each fallback can be scored
on exactly the data it would have been able to acquire - no new simulation.

Same machinery as run_band_study.py: brick-wall crop, same pipeline, same
detector, three error realisations per cell.

    python scripts/vna_fallback_study.py
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.stats.analysis import auc

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "bs", Path(__file__).resolve().parent / "run_band_study.py")
bs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bs)

BANDS = [
    ("LiteVNA-64, 3.0-6.3 GHz",      3.0e9, 6.3e9, "lite"),
    ("NanoVNA V2 Plus4, 3.0-4.4 GHz", 3.0e9, 4.4e9, "nano"),
]


def main() -> None:
    OUT = ROOT / "runs"
    rows = []
    for label, lo, hi, tag in BANDS:
        print(f"scoring {label} ...", flush=True)
        s = bs.gather(lo, hi)
        with open(OUT / f"band_scores_{tag}.csv", "w", newline="") as fh:
            fh.write("specimen,state,overlay,kerf,fractured,repeat,score\n")
            for x in s:
                fh.write(f"{x.specimen},{x.state},{x.overlay},{x.kerf},"
                         f"{x.fractured},{x.repeat},{x.score}\n")
        sc = np.array([x.score for x in s])
        fr = np.array([x.fractured for x in s])
        ov = np.array([x.overlay for x in s])
        gap = sc[fr].min() - sc[~fr].max()
        a = auc(sc, fr)
        by_ov = {o: sc[fr & (ov == o)].min() - sc[~fr & (ov == o)].max()
                 for o in sorted(set(ov))}
        res = bs.C0 / (2 * (hi - lo) * np.sqrt(bs.EPS_AVG)) * 1e3
        rows.append((label, (hi - lo) / 1e9, res, a, gap, by_ov))

    print()
    print("=" * 78)
    print("Cheap-VNA fallbacks, scored on the solved matrix")
    print("=" * 78)
    print(f"  {'VNA option':<34}{'BW':>6}{'res':>7}{'AUC':>8}{'sep':>8}")
    print(f"  {'3-11 GHz reference (full band)':<34}{8.00:>6.2f}{3.67:>7.2f}"
          f"{1.0:>8.4f}{40.8:>8.1f}")
    print(f"  {'4.35-11 GHz (first antenna)':<34}{6.65:>6.2f}{4.42:>7.2f}"
          f"{1.0:>8.4f}{17.9:>8.1f}")
    for label, bw, res, a, gap, _ in rows:
        print(f"  {label:<34}{bw:>6.2f}{res:>7.2f}{a:>8.4f}{gap:>8.1f}")
    print()
    print("  separation by overlay (dB):")
    print(f"  {'VNA option':<34}" + "".join(f"{o*1e3:>7.0f}mm" for o in rows[0][5]))
    for label, *_, by_ov in rows:
        print(f"  {label:<34}" + "".join(f"{v:>9.1f}" for v in by_ov.values()))
    print()
    print("  A negative separation means the classes OVERLAP at that")
    print("  overlay: some intact limb scores above some fractured one.")


if __name__ == "__main__":
    main()
