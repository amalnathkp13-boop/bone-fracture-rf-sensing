"""Which cells lose most when the low band goes.

The band study showed the global separation gap falling 40.8 -> 17.9 dB when
3.00-4.35 GHz is removed, while the worst corner I expected to bind - 0.2 mm
kerf under 10 mm of overlay - still cleared by 25.2 dB. A global minimum below
the supposed worst corner means the corner is not the binding case, so this
finds out which cells actually are.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import importlib.util
import numpy as np

from bonesim.experiment import N_REPEATS, build_matrix

spec = importlib.util.spec_from_file_location(
    "bs", Path(__file__).resolve().parent / "run_band_study.py")
bs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bs)

ROOT = Path(__file__).resolve().parent.parent


def run(f_lo, f_hi, tag):
    have = {p.stem: p for p in
            list((ROOT / "runs" / "matrix_colab").glob("*.npz"))
            + list((ROOT / "runs" / "matrix").glob("*.npz"))}
    rows = []
    for c in build_matrix():
        p = have.get(c.key)
        if p is None:
            continue
        for r in range(N_REPEATS):
            rows.append((c.specimen, c.state, c.overlay, c.kerf,
                         c.state != "intact", r,
                         bs.score_cell(p, r, f_lo, f_hi)))
    out = ROOT / "runs" / f"band_scores_{tag}.csv"
    with open(out, "w", newline="") as fh:
        fh.write("specimen,state,overlay,kerf,fractured,repeat,score" + chr(10))
        for x in rows:
            fh.write(",".join(str(v) for v in x) + chr(10))
    print(f"  wrote {out.name}, {len(rows)} scores", flush=True)
    return rows


def report(rows, label):
    st = np.array([r[1] for r in rows])
    ov = np.array([r[2] for r in rows])
    fr = np.array([r[4] for r in rows])
    sc = np.array([r[6] for r in rows])

    print()
    print("=" * 74)
    print(label)
    print("=" * 74)
    print(f"  {'state':<12}{'overlay':>9}{'n':>5}{'min':>9}{'mean':>9}")
    order = sorted({(s, o) for s, o in zip(st, ov)},
                   key=lambda t: (t[0], t[1]))
    worst = None
    for s, o in order:
        m = (st == s) & (ov == o)
        lo = sc[m].min()
        print(f"  {s:<12}{o*1e3:>7.0f}mm{m.sum():>5}{lo:>9.1f}{sc[m].mean():>9.1f}")
        if fr[m][0] and (worst is None or lo < worst[2]):
            worst = (s, o, lo)
    top_intact = sc[~fr].max()
    print()
    print(f"  weakest fractured cell : {worst[0]} at {worst[1]*1e3:.0f} mm "
          f"= {worst[2]:.1f} dB")
    print(f"  strongest intact cell  : {top_intact:.1f} dB")
    print(f"  margin                 : {worst[2] - top_intact:+.1f} dB")


if __name__ == "__main__":
    print("scoring the antenna band 4.35-11.0 GHz ...", flush=True)
    r = run(4.35e9, 11.0e9, "antenna")
    report(r, "Per-condition minima, antenna band 4.35-11.0 GHz")
