"""Is 8 dBi at 3 GHz reachable at all, and at what board size?

Aperture was tested and rejected: 60 -> 70 mm bought +0.72 dB of 3 GHz gain and
cost 6% of the match (99.69 -> 93.46% covered). So the remaining lever is
LENGTH, which is what sets endfire directivity.

The measured gain of the 150 mm design, read as gain against L/lambda:

    3 GHz   L/lambda 1.50    7.02 dBi
    5 GHz   L/lambda 2.50   11.87 dBi
    7 GHz   L/lambda 3.50   12.49 dBi
    9 GHz   L/lambda 4.50   12.06 dBi
   11 GHz   L/lambda 5.50    9.33 dBi

Interpolating the steep part, 8 dBi wants L/lambda about 1.70, which at 3 GHz
is a 170 mm antenna. That reading conflates length with aperture, both of which
change with frequency on a fixed antenna, so it is a hypothesis rather than an
answer - which is why this measures a real 170 mm antenna instead of trusting
it.

growth a*T is held at 2.0, the value the Stage 5 sweep identified as the one
parameter that actually mattered, so rate is rescaled for the longer taper
rather than left alone.

170 x 90 mm does NOT fit the 100 x 150 mm stock in the proposal's BOM. If this
works it is a choice for the reader, not a promotion: keep 150 mm and report
3 GHz at 7.02 dBi, or change the board and meet the specification.

    python scripts/tune_length_gain.py
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.antenna.model import bandwidth, pattern, run
from bonesim.antenna.vivaldi import uwb_3_11

SIM = Path("/root/bonesim-runs/gain_len170")
OUT = Path("/mnt/c/Users/ASUS/bonesim/runs/gain")
FREQ = np.linspace(2e9, 12e9, 401)
PROBES = [3e9, 5e9, 7e9, 9e9, 11e9]
LENGTH = 170.0


def main() -> None:
    base = uwb_3_11()
    taper = LENGTH - base.taper_start
    ant = dataclasses.replace(base, length=LENGTH, rate=2.0 / taper)
    print(f"  {LENGTH:.0f} x {ant.sub_width:.0f} mm, growth a*T = "
          f"{ant.growth:.2f}, aperture {ant.aperture:.0f} mm", flush=True)

    res = run(ant, SIM, FREQ, verbose=1, threads=8,
              end_criteria=1e-3, max_timesteps=30000, nf2ff_freqs=PROBES)

    db = 20 * np.log10(np.abs(res["s11"]))
    band = (FREQ >= 3e9) & (FREQ <= 11e9)
    lo, hi, _ = bandwidth(FREQ, res["s11"])

    rows = []
    for f in PROBES:
        th, gain, dmax = pattern(res, f)
        j = int(np.argmax(gain))
        rows.append({"f_GHz": f / 1e9, "gain_peak_dBi": float(gain[j]),
                     "s11_dB": float(np.interp(f, FREQ, db))})
        print(f"  {f/1e9:5.1f} GHz   peak {gain[j]:6.2f} dBi   "
              f"S11 {np.interp(f, FREQ, db):6.2f} dB", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "gain_len170.json").write_text(json.dumps(rows, indent=2))
    np.savez(OUT / "len170_s11.npz", f=FREQ, s11=res["s11"], z_in=res["z_in"])

    g3 = rows[0]["gain_peak_dBi"]
    covered = float((db[band] <= -10).mean())
    worst = float(db[band].max())
    print()
    print(f"  match {lo/1e9:.2f}-{hi/1e9:.2f} GHz, covered {covered*100:.2f}%, "
          f"worst {worst:.2f} dB")
    print(f"  3 GHz gain {g3:.2f} dBi   (150 mm gave 7.02, needs 8.00)")
    print()
    if g3 >= 8.0 and covered >= 0.99:
        print("  8 dBi at 3 GHz IS reachable, at 170 x 90 mm. The proposal's")
        print("  gain and board-size requirements are simply inconsistent at")
        print("  the bottom of the band; 20 mm of extra length resolves it.")
    elif g3 >= 8.0:
        print("  Gain met but the match regressed. Same trade as the aperture")
        print("  test. Not worth taking.")
    else:
        print("  Still short even at 170 mm. 8 dBi at 3 GHz is then not a")
        print("  board-size problem within any plausible size, and the")
        print("  requirement should be reported as unmet, not engineered at.")


if __name__ == "__main__":
    main()
