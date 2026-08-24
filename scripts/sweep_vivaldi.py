"""Retune the Vivaldi until it matches across 3-11 GHz.

The first-pass design (70 mm long, 40 mm aperture) matched only 4.0-6.4 GHz.
Proposal 2.3 gives an opening rate and nothing else, and the rate is not what
sets the low-frequency limit - the aperture and the total length are.

Rules of thumb for a tapered-slot antenna, in free-space wavelength at the
lowest frequency to be covered:

    aperture  >~ 0.5 lambda
    length    >~ 1.0 lambda

At 3 GHz that is 50 mm and 100 mm, against the 40 mm and 70 mm first tried. The
sweep below tests that reading. S11 only, no far-field box, so each point is
cheap.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.antenna.model import bandwidth, run
from bonesim.antenna.vivaldi import Vivaldi

SIM_ROOT = Path("/root/bonesim-runs/vivaldi_sweep")
FREQ = np.linspace(2e9, 12e9, 201)
BAND = (3e9, 11e9)

# length, aperture, sub_width, feed_width, rate
CANDIDATES = [
    ("baseline", 70.0, 40.0, 50.0, 3.0, 0.08),
    ("longer", 100.0, 40.0, 50.0, 3.0, 0.08),
    ("wider", 70.0, 55.0, 65.0, 3.0, 0.08),
    ("both", 110.0, 55.0, 65.0, 3.0, 0.06),
    ("both_narrowfeed", 110.0, 55.0, 65.0, 2.0, 0.06),
    ("both_slowrate", 110.0, 60.0, 70.0, 3.0, 0.05),
]


def main() -> int:
    SIM_ROOT.mkdir(parents=True, exist_ok=True)
    inband = (FREQ >= BAND[0]) & (FREQ <= BAND[1])

    print(f"{'name':<18}{'L':>6}{'ap':>6}{'rate':>6}{'-10dB band':>18}"
          f"{'worst':>8}{'mean':>8}{'covers':>8}{'s':>7}")
    best = None
    for name, length, ap, sw, fw, rate in CANDIDATES:
        ant = Vivaldi(length=length, aperture=ap, sub_width=sw,
                      feed_width=fw, rate=rate,
                      taper_start=min(20.0, length * 0.25))
        t0 = time.time()
        try:
            res = run(ant, SIM_ROOT / name, FREQ, verbose=0)
        except Exception as exc:                        # noqa: BLE001
            print(f"{name:<18} failed: {exc}")
            continue
        lo, hi, db = bandwidth(FREQ, res["s11"])
        span = "none" if lo is None else f"{lo/1e9:.2f}-{hi/1e9:.2f}"
        covers = lo is not None and lo <= BAND[0] and hi >= BAND[1]
        worst, mean = db[inband].max(), db[inband].mean()
        print(f"{name:<18}{length:>6.0f}{ap:>6.0f}{rate:>6.2f}{span:>18}"
              f"{worst:>8.1f}{mean:>8.1f}{('yes' if covers else 'no'):>8}"
              f"{time.time()-t0:>7.0f}")
        score = (covers, -worst)
        if best is None or score > best[0]:
            best = (score, name, ant, worst, span)

    if best is None:
        print("\nno candidate simulated")
        return 1
    (covers, _), name, ant, worst, span = best
    print(f"\nbest: {name}  ({span} GHz, worst in band {worst:.1f} dB)")
    print(ant.summary())
    if covers:
        print("\ncovers 3-11 GHz")
        return 0
    print("\nstill short of 3-11 GHz")
    return 1


if __name__ == "__main__":
    sys.exit(main())
