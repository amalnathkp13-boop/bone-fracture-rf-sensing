"""Stage 5: characterise the antipodal Vivaldi in openEMS.

Proposal 2.3 asks for the antenna to be simulated before it is etched, and makes
three claims this stage turns into measurements:

  1. "S11 < -10 dB across band, endfire, 8-10 dBi" (section 2.2 table)
  2. "FR4 is acceptable up to about 8 GHz and will cost you a few dB above that"
  3. "Rogers RO4350B is markedly better across the full band. If your budget
     allows one premium item, make it this."

Claim 3 is a spending decision on a INR 24k build - RO4350B plus fabrication is
roughly INR 6,500 against INR 3,300 for FR4 - so it is worth an hour of compute
rather than being taken on trust.

Resumable: results are cached per substrate, so an interrupted run resumes.
"""
from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.antenna.model import bandwidth, pattern, run
from bonesim.antenna.vivaldi import Vivaldi

# Cached results (small) live with the repo; the solver's field dumps do not.
RUNS = Path(__file__).resolve().parent.parent / "runs" / "stage5"
# openEMS writes its dumps here. Linux-native, because under WSL a path on
# /mnt/c is about an order of magnitude slower for this, and because the dumps
# are large enough to matter on a drive that is 95% full.
SIM_ROOT = Path("/root/bonesim-runs/stage5") if Path("/root").is_dir() else RUNS
BAND = (3e9, 11e9)
FREQ = np.linspace(2e9, 12e9, 201)
PROBE = (3e9, 5e9, 7e9, 9e9, 11e9)


def simulate(substrate: str, force: bool = False):
    cache = RUNS / f"{substrate}.pkl"
    if cache.exists() and not force:
        print(f"  {substrate:<10} (cached)")
        with open(cache, "rb") as fh:
            return pickle.load(fh)

    ant = Vivaldi(substrate=substrate)
    t0 = time.time()
    # Pattern frequencies must be fixed before the solve: this switches the
    # NF2FF box to frequency-domain recording. Left unset it dumps the full
    # time-domain field on six surfaces, about 1.8 GB per run.
    res = run(ant, SIM_ROOT / substrate, FREQ, verbose=0,
              nf2ff_freqs=PROBE)
    print(f"  {substrate:<10} {time.time()-t0:7.1f} s")

    # Far-field cuts have to be taken before the object is pickled, because the
    # NF2FF handle is not picklable and needs the simulation directory.
    res["patterns"] = {}
    for f in PROBE:
        try:
            th, gain, dmax = pattern(res, f)
            res["patterns"][f] = (th, gain, dmax)
        except Exception as exc:                       # noqa: BLE001
            print(f"    pattern at {f/1e9:g} GHz unavailable: {exc}")
    keep = {k: v for k, v in res.items() if not k.startswith("_")}
    keep["sim_path"] = str(keep["sim_path"])
    RUNS.mkdir(parents=True, exist_ok=True)
    with open(cache, "wb") as fh:
        pickle.dump(keep, fh)
    return keep


def main() -> int:
    RUNS.mkdir(parents=True, exist_ok=True)
    SIM_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"solver scratch: {SIM_ROOT}")
    print(Vivaldi().summary())
    print()
    print("=" * 72)
    print("Simulating")
    print("=" * 72)
    out = {s: simulate(s) for s in ("RO4350B", "FR4")}

    print()
    print("=" * 72)
    print("1. Match: is S11 below -10 dB across 3-11 GHz?")
    print("=" * 72)
    inband = (FREQ >= BAND[0]) & (FREQ <= BAND[1])
    print(f"  {'substrate':<11}{'-10dB band':>18}{'worst in band':>15}"
          f"{'mean in band':>14}{'covers 3-11':>13}")
    for name, res in out.items():
        lo, hi, db = bandwidth(FREQ, res["s11"])
        span = "none" if lo is None else f"{lo/1e9:.2f}-{hi/1e9:.2f} GHz"
        worst, mean = db[inband].max(), db[inband].mean()
        covers = (lo is not None and lo <= BAND[0] and hi >= BAND[1])
        print(f"  {name:<11}{span:>18}{worst:>14.1f}{mean:>14.1f}"
              f"{('yes' if covers else 'NO'):>13}")

    print()
    print("=" * 72)
    print("2. The substrate decision (proposal 2.3)")
    print("=" * 72)
    ro, fr = out["RO4350B"], out["FR4"]
    db_ro = 20 * np.log10(np.abs(ro["s11"]) + 1e-30)
    db_fr = 20 * np.log10(np.abs(fr["s11"]) + 1e-30)
    print(f"  {'f (GHz)':>9}{'RO4350B':>11}{'FR4':>10}{'penalty':>10}")
    for f in PROBE:
        i = int(np.argmin(np.abs(FREQ - f)))
        print(f"  {FREQ[i]/1e9:>9.1f}{db_ro[i]:>11.1f}{db_fr[i]:>10.1f}"
              f"{db_fr[i]-db_ro[i]:>+10.1f}")
    below8 = inband & (FREQ <= 8e9)
    above8 = inband & (FREQ > 8e9)
    print(f"\n  mean |S11| below 8 GHz: RO {db_ro[below8].mean():.1f} dB, "
          f"FR4 {db_fr[below8].mean():.1f} dB")
    print(f"  mean |S11| above 8 GHz: RO {db_ro[above8].mean():.1f} dB, "
          f"FR4 {db_fr[above8].mean():.1f} dB")

    print()
    print("=" * 72)
    print("3. Gain (proposal 2.2 specifies 8-10 dBi, endfire)")
    print("=" * 72)
    print(f"  {'f (GHz)':>9}{'RO4350B':>11}{'FR4':>10}")
    for f in PROBE:
        row = [f"{f/1e9:>9.1f}"]
        for name in ("RO4350B", "FR4"):
            p = out[name].get("patterns", {}).get(f)
            row.append(f"{p[2]:>11.1f}" if p else f"{'-':>11}")
        print("  " + "".join(row))

    print()
    lo_ro, hi_ro, _ = bandwidth(FREQ, ro["s11"])
    ok = lo_ro is not None and lo_ro <= BAND[0] and hi_ro >= BAND[1]
    print("STAGE 5 PASS - the antenna matches across the working band."
          if ok else
          "STAGE 5 FAIL - the design does not cover 3-11 GHz; retune the\n"
          "  aperture (low end) or the opening rate and feed width (high end).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
