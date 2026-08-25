"""Match the 3-4.4 GHz plateau with a tapered feed, not corrugations.

Stage 5 diagnosed the low-frequency shortfall as edge-current resonance and
prescribed corrugations. Retrying them properly (scripts/retry_corrugations.py)
refuted that: they converge fine, and they do not move the low end.

The S11 and impedance sweeps point somewhere else entirely. The plain design is
not cut off below 4.35 GHz - it is MISMATCHED:

    2.225-2.725 GHz   matched, -33 dB at 2.475      Re(Zin) 49.4 ohm
    ~3.0 GHz          -6.6 dB, a narrow spike       Re(Zin) 113  ohm
    3.25-4.40 GHz     -8 to -10 dB, a flat plateau  Re(Zin) 24-37 ohm

The plateau is arithmetic, not physics: 24.4 ohm into a 50 ohm feed gives
Gamma = (24.4-50)/(24.4+50) = -0.34 = -9.3 dB, which is the measured -9.14 dB
at 4.0 GHz. The antenna radiates there perfectly well. The feed is presenting
the wrong impedance.

That is a transformer problem, and vivaldi.py already records the lever:
median Re(Zin) is 43 / 29 / 19 ohm for feed widths of 1.5 / 3.0 / 5.0 mm. Width
buys impedance predictably, so a linear taper - wide where it meets the flare,
50 ohm at the port - transforms the antenna's ~30 ohm up toward 50.

Sizing. A quarter wave at 3.8 GHz, the centre of the plateau, is about 12 mm on
RO4350B (eps_eff ~ 2.7, lambda_g ~ 48 mm). The as-built feed is 8 mm, which is
0.17 lambda - short for a transformer, so feed length is varied too.

    python scripts/tune_feed_taper.py <variant>
    python scripts/tune_feed_taper.py --summary
"""
from __future__ import annotations

import dataclasses
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.antenna.model import bandwidth, run
from bonesim.antenna.vivaldi import uwb_3_11

SIM_ROOT = Path("/root/bonesim-runs/feedtaper")
OUT = Path("/mnt/c/Users/ASUS/bonesim/runs/feedtaper")
FREQ = np.linspace(2e9, 12e9, 401)
BAND = (3e9, 11e9)
END_CRITERIA = 1e-3
MAX_TS = 30000

# (feed_width at the flare, feed_width_port at the SMA, feed_len)
# feed_width_port stays 1.74 mm throughout: that is 50 ohm microstrip on this
# substrate and it is what the SMA has to see.
VARIANTS = {
    # First pass, WIDER at the flare. This was the wrong direction and the
    # answer was already in vivaldi.py: median Re(Zin) is 43 / 29 / 19 ohm for
    # feed widths of 1.5 / 3.0 / 5.0 mm, so Zin falls as width rises. The
    # plateau needs Zin RAISED from 24 ohm toward 50, so the flare end has to
    # get narrower. Kept, because measuring the wrong direction is what
    # established the gradient is real and monotonic.
    "t275_l08": (2.75, 1.74, 8.0),
    "t275_l12": (2.75, 1.74, 12.0),
    "t350_l12": (3.50, 1.74, 12.0),
    # Second pass, WIDER still. The first three points looked like a failure
    # until the third landed: Re(Zin) at 4 GHz rises monotonically with the
    # flare-end width, 24.4 / 24.5 / 25.9 / 29.1 ohm for 1.74 / 2.75 / 2.75 /
    # 3.50 mm, and 3.50 mm covers 94% of 3-11 GHz against the baseline's 84%.
    #
    # The vivaldi.py calibration (43 / 29 / 19 ohm for 1.5 / 3.0 / 5.0 mm) runs
    # the OTHER way, and that is not a contradiction: it describes a UNIFORM
    # line, where widening lowers the line impedance everywhere. Here the port
    # is pinned at 1.74 mm, so widening the flare end steepens a taper instead
    # of shifting a uniform line, and a taper transforms upward.
    "w400_l12": (4.00, 1.74, 12.0),
    "w450_l12": (4.50, 1.74, 12.0),
}


def make(name):
    fw, fwp, flen = VARIANTS[name]
    return dataclasses.replace(uwb_3_11(), feed_width=fw,
                               feed_width_port=fwp, feed_len=flen)


def one(name: str) -> dict:
    ant = make(name)
    t0 = time.time()
    res = run(ant, SIM_ROOT / name, FREQ, verbose=1, threads=8,
              end_criteria=END_CRITERIA, max_timesteps=MAX_TS,
              nf2ff_freqs=None)
    dt = time.time() - t0

    s11, z = res["s11"], res["z_in"]
    db = 20 * np.log10(np.abs(s11))
    lo, hi, _ = bandwidth(FREQ, s11)
    inb = (FREQ >= BAND[0]) & (FREQ <= BAND[1])
    plateau = (FREQ >= 3.25e9) & (FREQ <= 4.40e9)

    out = {
        "name": name,
        "feed_width": VARIANTS[name][0],
        "feed_width_port": VARIANTS[name][1],
        "feed_len": VARIANTS[name][2],
        "band_lo_GHz": None if lo is None else lo / 1e9,
        "band_hi_GHz": None if hi is None else hi / 1e9,
        "mean_db_in_band": float(db[inb].mean()),
        "worst_db_in_band": float(db[inb].max()),
        "worst_db_on_plateau": float(db[plateau].max()),
        "mean_db_on_plateau": float(db[plateau].mean()),
        "frac_below_10dB_in_band": float((db[inb] <= -10).mean()),
        "db_at_3GHz": float(np.interp(3e9, FREQ, db)),
        "db_at_3p5GHz": float(np.interp(3.5e9, FREQ, db)),
        "db_at_4GHz": float(np.interp(4e9, FREQ, db)),
        "re_zin_3GHz": float(np.interp(3e9, FREQ, z.real)),
        "re_zin_4GHz": float(np.interp(4e9, FREQ, z.real)),
        "median_re_zin": float(np.median(z[inb].real)),
        "seconds": dt,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(out, indent=2))
    np.savez(OUT / f"{name}_s11.npz", f=FREQ, s11=s11, z_in=z)
    print(json.dumps(out, indent=2), flush=True)
    return out


def summary() -> None:
    rows = [json.loads((OUT / f"{n}.json").read_text())
            for n in VARIANTS if (OUT / f"{n}.json").exists()]
    if not rows:
        print("nothing to summarise yet")
        return
    print()
    print("=" * 88)
    print("Feed taper against the 3.25-4.40 GHz plateau")
    print("=" * 88)
    print(f"  {'variant':<10}{'w_fl':>6}{'w_pt':>6}{'len':>6}"
          f"{'-10dB band':>14}{'plateau worst':>15}{'ReZ 4G':>8}"
          f"{'covered':>9}{'min':>6}")
    print(f"  {'BASELINE':<10}{1.74:>6.2f}{1.74:>6.2f}{8.0:>6.1f}"
          f"{'4.40-12.00':>14}{-8.42:>15.2f}{24.4:>8.1f}"
          f"{'':>9}{9.6:>6.1f}")
    for r in rows:
        span = ("none" if r["band_lo_GHz"] is None
                else f"{r['band_lo_GHz']:.2f}-{r['band_hi_GHz']:.2f}")
        print(f"  {r['name']:<10}{r['feed_width']:>6.2f}"
              f"{r['feed_width_port']:>6.2f}{r['feed_len']:>6.1f}{span:>14}"
              f"{r['worst_db_on_plateau']:>15.2f}{r['re_zin_4GHz']:>8.1f}"
              f"{r['frac_below_10dB_in_band']*100:>8.0f}%{r['seconds']/60:>6.1f}")
    print()
    print("  plateau worst = the highest S11 anywhere in 3.25-4.40 GHz.")
    print("  The baseline sits at -8.42 dB there, so anything below -10 has")
    print("  closed the gap. 'covered' is the fraction of 3-11 GHz under -10 dB.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--summary":
        summary()
    elif len(sys.argv) > 1:
        one(sys.argv[1])
    else:
        print(__doc__)
        print("variants:", ", ".join(VARIANTS))
