"""Collect every number the report quotes into one committed JSON file.

The report reads its figures from this file rather than having them typed into
the text, so it cannot drift from the analysis. That only works if the file
itself is reproducible and committed - it was originally produced by an ad-hoc
command that lived nowhere, which meant a clean clone could not rebuild the
report at all.

Inputs are the solved matrix and the antenna sweeps under runs/, which are too
large to host. The output is 1 kB and IS committed, so the report builds from a
fresh clone with no solver and no simulation data.

    python scripts/collect_report_numbers.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
OUT = ROOT / "results" / "report_numbers.json"


def main() -> int:
    need = [RUNS / "stage7_scores.csv",
            RUNS / "feedtaper" / "w450_l12.json",
            RUNS / "gain" / "gain_tapered.json"]
    missing = [p for p in need if not p.exists()]
    if missing:
        print("cannot collect; these are produced by the analysis scripts and "
              "are not in the repository:")
        for p in missing:
            print("   ", p.relative_to(ROOT))
        print("\nThe committed results/report_numbers.json already holds the "
              "published values, so the report still builds without them.")
        return 1

    rows = list(csv.reader(open(need[0])))[1:]
    sc = np.array([float(r[6]) for r in rows])
    fr = np.array([r[4] == "True" for r in rows])
    ov = np.array([float(r[2]) for r in rows])

    out = {
        "n_scores": len(rows),
        "intact": [int((~fr).sum()), float(sc[~fr].min()),
                   float(np.median(sc[~fr])), float(sc[~fr].max())],
        "fract": [int(fr.sum()), float(sc[fr].min()),
                  float(np.median(sc[fr])), float(sc[fr].max())],
        "gap": float(sc[fr].min() - sc[~fr].max()),
        "intact_by_ov": {f"{o*1e3:.0f}": round(float(sc[~fr & (ov == o)].mean()), 1)
                         for o in sorted(set(ov))},
        "antenna": {k: (round(v, 3) if isinstance(v, float) else v)
                    for k, v in json.loads(need[1].read_text()).items()},
        "gain": [(r["f_GHz"], round(r["gain_peak_dBi"], 2))
                 for r in json.loads(need[2].read_text())],
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  {out['n_scores']} scores, separation {out['gap']:.1f} dB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
