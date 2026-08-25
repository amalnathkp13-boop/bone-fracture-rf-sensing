"""Corrugations, retried with an end criterion suited to a ringing structure.

Stage 5 abandoned corrugations after a 40-hour extrapolated runtime. The cause
was not mesh - 7.40 M cells either way, identical time step - but convergence:
the slots are resonant by design, so stored energy will not decay to the -40 dB
criterion written for a structure that does not ring.

This retries them shallower and fewer, at -30 dB.

THE CONTROL IS THE POINT. Relaxing the end criterion stops the solve with more
energy still in the box, which truncates the port waveform and distorts S11 by
spectral leakage - worst at the low frequencies this whole exercise is about.
So a PLAIN run at the same relaxed criterion is included. Without it, any
improvement is uninterpretable: it could be the corrugations, or it could be
truncation moving the curve. The plain design's -40 dB result is known
(4.35-12.00 GHz), so the plain -30 dB run measures the truncation error
directly.

    python scripts/retry_corrugations.py <variant>
    python scripts/retry_corrugations.py --summary
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.antenna.model import bandwidth, run
from bonesim.antenna.vivaldi import Vivaldi, uwb_3_11

SIM_ROOT = Path("/root/bonesim-runs/corrugations")
OUT = Path("/mnt/c/Users/ASUS/bonesim/runs/corrugations")
FREQ = np.linspace(2e9, 12e9, 401)
BAND = (3e9, 11e9)
END_CRITERIA = 1e-3          # -30 dB, against the -40 dB of Stage 5
MAX_TS = 30000

# (name, n_corrugations, depth mm, width mm)
VARIANTS = {
    "plain_e3":  (0, 0.0, 0.0),     # the control: truncation error, alone
    "corr4_d4":  (4, 4.0, 3.0),     # shallower and fewer, as Stage 5 advised
    "corr6_d6":  (6, 6.0, 3.0),     # midway to the original 8 mm
}


def make(name: str) -> Vivaldi:
    """Vivaldi is frozen, so vary the slots with dataclasses.replace."""
    import dataclasses
    n, depth, width = VARIANTS[name]
    ant = uwb_3_11(corrugations=n)
    if n:
        ant = dataclasses.replace(ant, corr_depth=depth, corr_width=width)
    return ant


def one(name: str) -> dict:
    ant = make(name)
    t0 = time.time()
    res = run(ant, SIM_ROOT / name, FREQ, verbose=1, threads=8,
              end_criteria=END_CRITERIA, max_timesteps=MAX_TS,
              nf2ff_freqs=None)
    dt = time.time() - t0

    s11 = res["s11"]
    z = res["z_in"]
    lo, hi, _ = bandwidth(FREQ, s11)
    inb = (FREQ >= BAND[0]) & (FREQ <= BAND[1])
    db = 20 * np.log10(np.abs(s11))

    def at(f):
        return float(np.interp(f, FREQ, z.real))

    out = {
        "name": name,
        "n_corr": VARIANTS[name][0],
        "depth": VARIANTS[name][1],
        "width": VARIANTS[name][2],
        "band_lo_GHz": None if lo is None else lo / 1e9,
        "band_hi_GHz": None if hi is None else hi / 1e9,
        "mean_db_in_band": float(db[inb].mean()),
        "worst_db_in_band": float(db[inb].max()),
        "db_at_3GHz": float(np.interp(3e9, FREQ, db)),
        "db_at_3p5GHz": float(np.interp(3.5e9, FREQ, db)),
        "db_at_4GHz": float(np.interp(4e9, FREQ, db)),
        "re_zin_3GHz": at(3e9),
        "re_zin_4GHz": at(4e9),
        "seconds": dt,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(out, indent=2))
    np.savez(OUT / f"{name}_s11.npz", f=FREQ, s11=s11, z_in=z)
    print(json.dumps(out, indent=2), flush=True)
    return out


def summary() -> None:
    rows = []
    for n in VARIANTS:
        p = OUT / f"{n}.json"
        if p.exists():
            rows.append(json.loads(p.read_text()))
    if not rows:
        print("nothing to summarise yet")
        return

    print()
    print("=" * 86)
    print("Corrugations at EndCriteria -30 dB, against Stage 5's -40 dB plain run")
    print("=" * 86)
    print(f"  {'variant':<11}{'slots':>6}{'depth':>7}{'-10dB band':>15}"
          f"{'mean':>8}{'@3.0':>8}{'@3.5':>8}{'ReZ 3G':>8}{'min':>7}")
    print(f"  {'':<11}{'':>6}{'mm':>7}{'GHz':>15}{'dB':>8}{'dB':>8}"
          f"{'dB':>8}{'ohm':>8}{'':>7}")
    print(f"  {'STAGE 5':<11}{0:>6}{'-':>7}{'4.35-12.00':>15}"
          f"{-14.9:>8.1f}{'-':>8}{'-':>8}{117:>8.0f}{13.2:>7.1f}")
    for r in rows:
        span = ("none" if r["band_lo_GHz"] is None
                else f"{r['band_lo_GHz']:.2f}-{r['band_hi_GHz']:.2f}")
        print(f"  {r['name']:<11}{r['n_corr']:>6}{r['depth']:>7.1f}{span:>15}"
              f"{r['mean_db_in_band']:>8.1f}{r['db_at_3GHz']:>8.1f}"
              f"{r['db_at_3p5GHz']:>8.1f}{r['re_zin_3GHz']:>8.0f}"
              f"{r['seconds']/60:>7.1f}")

    ctl = next((r for r in rows if r["name"] == "plain_e3"), None)
    if ctl is None:
        print()
        print("  NO CONTROL YET. Until plain_e3 finishes, none of the")
        print("  corrugated rows can be attributed to the corrugations.")
        return

    print()
    print("  Read the control row first. Stage 5's plain design at -40 dB gave")
    print("  4.35-12.00 GHz. Any difference in plain_e3 is truncation error")
    print("  from the relaxed criterion, and is the yardstick every corrugated")
    print("  row has to beat before it means anything.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--summary":
        summary()
    elif len(sys.argv) > 1:
        one(sys.argv[1])
    else:
        print(__doc__)
        print("variants:", ", ".join(VARIANTS))
