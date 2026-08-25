"""Gain of the tapered design, against proposal 2.2's 8-10 dBi.

The gain row in docs/stage5-findings.md was measured on the UNIFORM-feed
antenna. Promoting the tapered design invalidated it: the feed changed, the
match changed across the whole band, and an antenna that reflects less
radiates more. Carrying the old number forward would be reporting a
measurement of a different antenna.

NF2FF is recorded at a fixed frequency list rather than in the time domain.
Without an explicit list the box stores the field on all six surfaces at every
timestep, about 1.8 GB per run here; with one it is a few hundred kB.

    python scripts/measure_gain.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.antenna.model import bandwidth, pattern, run
from bonesim.antenna.vivaldi import uwb_3_11

SIM = Path("/root/bonesim-runs/gain_tapered")
OUT = Path("/mnt/c/Users/ASUS/bonesim/runs/gain")
FREQ = np.linspace(2e9, 12e9, 401)
PROBES = [3e9, 5e9, 7e9, 9e9, 11e9]


def main() -> None:
    ant = uwb_3_11()
    res = run(ant, SIM, FREQ, verbose=1, threads=8,
              end_criteria=1e-3, max_timesteps=30000,
              nf2ff_freqs=PROBES)

    db = 20 * np.log10(np.abs(res["s11"]))
    rows = []
    for f in PROBES:
        th, gain, dmax = pattern(res, f)
        # Boresight is +x, which is theta = 0 in this cut.
        j = int(np.argmin(np.abs(th)))
        rows.append({
            "f_GHz": f / 1e9,
            "gain_boresight_dBi": float(gain[j]),
            "directivity_dBi": float(dmax),
            "s11_dB": float(np.interp(f, FREQ, db)),
        })
        print(f"  {f/1e9:5.1f} GHz   boresight {gain[j]:6.2f} dBi   "
              f"Dmax {dmax:6.2f} dBi   S11 {np.interp(f, FREQ, db):6.2f} dB",
              flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "gain_tapered.json").write_text(json.dumps(rows, indent=2))

    g = [r["gain_boresight_dBi"] for r in rows]
    lo, hi, _ = bandwidth(FREQ, res["s11"])
    print()
    print(f"  match {lo/1e9:.2f}-{hi/1e9:.2f} GHz")
    print(f"  gain {min(g):.1f} to {max(g):.1f} dBi across 3-11 GHz")
    n_met = sum(1 for x in g if x >= 8.0)
    print(f"  proposal 2.2 asks 8-10 dBi: met at {n_met}/{len(g)} probe "
          f"frequencies")
    if n_met < len(g):
        print("  Not met across the whole band. A 150 mm aperture is "
              "electrically")
        print("  small at 3 GHz - 1.5 wavelengths - so low-end gain is bounded")
        print("  by size, not by the match. Report it, do not hide it.")


if __name__ == "__main__":
    main()
