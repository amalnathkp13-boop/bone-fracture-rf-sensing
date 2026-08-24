"""Stage 0 acceptance test.

Confirms the gprMax toolchain returns a physically correct result, not merely
that it runs. Two echoes are predicted analytically from the geometry in
scripts/gen_smoketest.py and located in differenced receiver traces:

    A - B   the buried PEC rod
    B - C   the air/slab interface

Differencing is required: the excitation pulse is roughly 140 ps wide while the
echoes arrive 33-170 ps after t0, so source self-coupling buries both targets in
the raw trace. This mirrors the empty-scene subtraction of proposal 2.5 step 3,
so passing this test exercises the real method rather than a toy version of it.

Arrival times are referenced to the direct-coupling first break of the free-space
scene, not to t = 0. gprMax's gaussiandot waveform is centred at chi = 1/f
(143 ps at 7 GHz), so absolute sample indices carry that offset. Because source
and receiver are co-located, the direct break is the zero-path event, and using
it as the reference cancels the waveform origin exactly - the simulation
equivalent of referencing a VNA to its calibration plane (proposal 2.5 step 1).
"""
import sys
from pathlib import Path

import numpy as np
import h5py

C0 = 299_792_458.0

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_smoketest import (ANT_Y, SLAB_Y1, ROD_Y, ROD_R, SLAB_EPS, DX)

# Round-trip arrival times, from the scattering surface nearest the antenna.
T_SLAB = 2 * (ANT_Y - SLAB_Y1) / C0
T_ROD = 2 * ((ANT_Y - SLAB_Y1) / C0
             + (SLAB_Y1 - (ROD_Y + ROD_R)) * np.sqrt(SLAB_EPS) / C0)


def load(path):
    with h5py.File(path, "r") as f:
        return (np.asarray(f["/rxs/rx1/Ez"][:], dtype=float),
                float(f.attrs["dt"]))


def arrival(trace, t):
    """First-break time: earliest crossing of 20% of the envelope maximum.

    Peak-picking is wrong here - a dispersive echo peaks after it arrives.
    """
    env = np.abs(trace)
    thr = 0.2 * env.max()
    idx = np.argmax(env > thr)
    return t[idx], env.max()


def main(run_dir: str) -> int:
    d = Path(run_dir)
    a, dt = load(d / "smoketest_A_rod.out")
    b, _ = load(d / "smoketest_B_slab.out")
    c, _ = load(d / "smoketest_C_free.out")
    t = np.arange(a.size) * dt

    rod_sig, slab_sig = a - b, b - c
    direct = np.abs(c).max()

    # Zero-path reference: source and rx are co-located, so the direct break in
    # the target-free scene marks t = 0 of propagation.
    t0, _ = arrival(c, t)

    print(f"time step         {dt*1e15:8.2f} fs  ({a.size} iterations, "
          f"{t[-1]*1e9:.2f} ns)")
    print(f"direct coupling   {direct:.3e} V/m  (scene C, no targets)")
    print(f"waveform origin   {t0*1e12:.1f} ps  (subtracted from all arrivals)")
    print()
    hdr = f"{'echo':<14}{'predicted':>12}{'measured':>12}{'error':>10}{'residual':>12}{'vs direct':>11}"
    print(hdr)

    # One grid cell of two-way path in the slab is the resolution floor.
    tol = 2 * DX * np.sqrt(SLAB_EPS) / C0
    ok = True
    for name, tp, sig in (("slab surface", T_SLAB, slab_sig),
                          ("PEC rod", T_ROD, rod_sig)):
        tm_abs, amp = arrival(sig, t)
        tm = tm_abs - t0
        err = abs(tm - tp)
        good = err < max(tol, 2 * dt)
        ok &= good
        print(f"{name:<14}{tp*1e12:10.1f} ps{tm*1e12:10.1f} ps{err*1e12:8.1f} ps"
              f"{amp:12.3e}{amp/direct:10.1%}"
              f"{'' if good else '  <-- OUT OF TOLERANCE'}")

    print(f"\ntolerance         {max(tol, 2*dt)*1e12:.1f} ps "
          f"(one cell two-way in eps_r={SLAB_EPS:g}, floored at 2 dt)")
    if ok:
        print("\nSTAGE 0 PASS - solver reproduces both predicted echoes.")
        return 0
    print("\nSTAGE 0 FAIL - see above.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
