"""Close the last gap: 7.02 dBi at 3 GHz against proposal 2.2's 8-10 dBi.

Every other requirement is met. The tapered feed already took 3 GHz gain from
3.7 to 7.02 dBi, because an antenna that reflects less radiates more, but the
last decibel is an APERTURE problem rather than a match problem: at 3 GHz the
150 mm antenna is 1.5 wavelengths long and the mouth is 0.6 wavelengths wide.

The mouth can still grow. Widening the aperture 60 -> 70 mm on a 90 -> 100 mm
board keeps the arms at 15 mm - Stage 5 fix 4, which was what took the design
from 5.35-8.60 to 4.35-12.00 GHz - and 150 x 100 mm is still inside the stock
already in the bill of materials.

The risk is real and worth stating: Stage 5's sweep found the match got WORSE
as aperture grew. That was with a uniform feed and a different failure mode, so
it may not carry over, but this run measures S11 as well as gain and the design
only changes if BOTH hold.

    python scripts/tune_low_gain.py
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

SIM = Path("/root/bonesim-runs/gain_ap70")
OUT = Path("/mnt/c/Users/ASUS/bonesim/runs/gain")
FREQ = np.linspace(2e9, 12e9, 401)
PROBES = [3e9, 5e9, 7e9, 9e9, 11e9]


def main() -> None:
    ant = dataclasses.replace(uwb_3_11(), aperture=70.0, sub_width=100.0)
    res = run(ant, SIM, FREQ, verbose=1, threads=8,
              end_criteria=1e-3, max_timesteps=30000, nf2ff_freqs=PROBES)

    db = 20 * np.log10(np.abs(res["s11"]))
    band = (FREQ >= 3e9) & (FREQ <= 11e9)
    lo, hi, _ = bandwidth(FREQ, res["s11"])

    rows = []
    for f in PROBES:
        th, gain, dmax = pattern(res, f)
        j = int(np.argmax(gain))     # endfire peak, not theta = 0
        rows.append({"f_GHz": f / 1e9, "gain_peak_dBi": float(gain[j]),
                     "peak_theta_deg": float(th[j]),
                     "s11_dB": float(np.interp(f, FREQ, db))})
        print(f"  {f/1e9:5.1f} GHz   peak {gain[j]:6.2f} dBi at theta "
              f"{th[j]:+6.1f}   S11 {np.interp(f, FREQ, db):6.2f} dB", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "gain_ap70.json").write_text(json.dumps(rows, indent=2))
    np.savez(OUT / "ap70_s11.npz", f=FREQ, s11=res["s11"], z_in=res["z_in"])

    g3 = rows[0]["gain_peak_dBi"]
    covered = float((db[band] <= -10).mean())
    worst = float(db[band].max())
    print()
    print(f"  match {lo/1e9:.2f}-{hi/1e9:.2f} GHz, covered {covered*100:.2f}%, "
          f"worst {worst:.2f} dB")
    print(f"  3 GHz gain {g3:.2f} dBi (was 7.02 at aperture 60)")
    print()
    print("  BASELINE to beat: covered 99.69%, worst -9.98 dB, 3 GHz 7.02 dBi")
    if g3 >= 8.0 and covered >= 0.99 and worst <= -9.9:
        print("  ADOPT: gain requirement met without giving up the match.")
    elif g3 >= 8.0:
        print("  Gain met, but the match regressed. This is the trade Stage 5's")
        print("  sweep warned about. Do NOT adopt on the gain number alone.")
    else:
        print("  Gain still short. The aperture is not the binding constraint,")
        print("  or 10 mm of it is not enough. Report 3 GHz as unmet.")


if __name__ == "__main__":
    main()
