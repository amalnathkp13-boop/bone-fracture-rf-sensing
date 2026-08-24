"""Retune the Vivaldi until it matches across 3-11 GHz.

The first sweep varied length, aperture and opening rate and failed everywhere,
with a matched band of about 1 GHz that moved with geometry instead of widening.
Two defects were found and fixed along the way (a feed that was two plates
rather than a transmission line, and an absorbing boundary inside the near
field), but neither changed the bandwidth.

The reason turned out to be a parameter proposal 2.3 never mentions. What sets
the flare profile is not the opening rate `a` but the dimensionless product
`a * T`, where T is the taper length. An exponential of fixed total growth has
the same shape however far it is stretched, so a rate quoted without a taper
length does not specify anything.

Every earlier configuration had a*T between 4 and 6.4, which pushes the whole
flare into the last few millimetres: the slot opened from nothing to its full
mouth over a distance *shorter than the mouth itself*, an opening angle beyond
sixty degrees. That reflects rather than radiates. It also explains why making
the antenna longer at fixed rate made things worse - it raised a*T from 4.0
to 6.4.

This sweep holds the length and aperture fixed and varies a*T directly, which
is the hypothesis stated as an experiment: lower a*T should lengthen the flare
and widen the match.
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

LENGTH, TAPER_START = 120.0, 18.0
APERTURE, SUB_WIDTH = 44.0, 54.0
T = LENGTH - TAPER_START

# a*T values to test. 4.0 reproduces the earlier failures for comparison.
GROWTH = [1.5, 2.0, 2.5, 3.0, 4.0]


def main() -> int:
    SIM_ROOT.mkdir(parents=True, exist_ok=True)
    inband = (FREQ >= BAND[0]) & (FREQ <= BAND[1])

    print(f"L={LENGTH:g} mm, taper {T:g} mm, aperture={APERTURE:g} mm, "
          f"RO4350B\n")
    print(f"{'a*T':>6}{'rate':>8}{'flare':>8}{'fl/ap':>7}"
          f"{'-10dB band':>16}{'worst':>8}{'mean':>8}{'covers':>8}{'s':>6}")
    best = None
    for g in GROWTH:
        ant = Vivaldi(length=LENGTH, taper_start=TAPER_START,
                      aperture=APERTURE, sub_width=SUB_WIDTH, rate=g / T)
        t0 = time.time()
        try:
            res = run(ant, SIM_ROOT / f"g{g:g}", FREQ, verbose=0)
        except Exception as exc:                        # noqa: BLE001
            print(f"{g:>6.1f}  failed: {exc}")
            continue
        lo, hi, db = bandwidth(FREQ, res["s11"])
        span = "none" if lo is None else f"{lo/1e9:.2f}-{hi/1e9:.2f}"
        covers = lo is not None and lo <= BAND[0] and hi >= BAND[1]
        worst, mean = db[inband].max(), db[inband].mean()
        print(f"{g:>6.1f}{ant.rate:>8.4f}{ant.flare_length:>8.1f}"
              f"{ant.flare_ratio:>7.2f}{span:>16}{worst:>8.1f}{mean:>8.1f}"
              f"{('yes' if covers else 'no'):>8}{time.time()-t0:>6.0f}")
        score = (covers, -worst)
        if best is None or score > best[0]:
            best = (score, g, ant, worst, span, lo, hi)

    if best is None:
        print("\nno candidate simulated")
        return 1
    (covers, _), g, ant, worst, span, lo, hi = best
    print(f"\nbest: a*T = {g:g}  ({span} GHz, worst in band {worst:.1f} dB)")
    print(ant.summary())
    print(f"  flare {ant.flare_length:.1f} mm over a {ant.aperture:g} mm "
          f"mouth, ratio {ant.flare_ratio:.2f}")
    if covers:
        print("\ncovers 3-11 GHz")
        return 0
    print("\nstill short of 3-11 GHz")
    return 1


if __name__ == "__main__":
    sys.exit(main())
