"""Stage 1 end-to-end check: does gprMax reproduce the tissue physics?

Fitting a Debye model in Python and finding it matches Cole-Cole in Python
proves nothing about the solver. This measures the material *inside gprMax*.

Method. Fill a 2D domain entirely with one tissue and place two receivers on
axis at radii r1 and r2 from a line source. The exact 2D Green's function for a
z-directed line current is the Hankel function of the second kind, so

    H(f) = FFT(rx2) / FFT(rx1) = H0^(2)(k r2) / H0^(2)(k r1),
    k(f)  = 2 pi f sqrt(eps*(f)) / c,   eps* from the Cole-Cole model

with no plane-wave assumption, no interfaces and no multiple reflections to
model. Magnitude tests conductivity (attenuation), phase tests permittivity
(velocity), and both are tested across the whole 3-11 GHz band at once.

The comparison is against Cole-Cole, not against the Debye fit, so this
validates the fit and the solver's dispersive update together.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import h5py
from scipy.special import hankel2

from bonesim.materials import tissues as T
from bonesim.materials.debye import fit_debye

C0 = 299_792_458.0
F_LO, F_HI = 3e9, 11e9
DX = 0.0002
DOM = (0.100, 0.060)
SRC = (0.020, 0.030)
# Receiver radii. The separation is deliberately short: muscle has a field
# penetration depth of only 2.9 mm at 11 GHz, so a long baseline drives the
# band-edge bins below the solver's numerical noise floor and the magnitude
# comparison then measures noise rather than the material.
R1, R2 = 0.015, 0.020
TW = 2.0e-9
TISSUE = "muscle"


def write_models(out_dir: Path) -> None:
    dt = DX / (C0 * np.sqrt(2))
    fit = fit_debye(T.get(TISSUE), F_LO, F_HI, n_poles=2, tau_min=2 * dt)
    body = (f"#title: homogeneous {TISSUE}, two-receiver propagation test\n\n"
            f"#domain: {DOM[0]:.4f} {DOM[1]:.4f} {DX:.4f}\n"
            f"#dx_dy_dz: {DX:.4f} {DX:.4f} {DX:.4f}\n"
            f"#time_window: {TW:g}\n\n"
            f"{fit.gprmax_cards(dt=dt)}\n"
            f"#box: 0 0 0 {DOM[0]:.4f} {DOM[1]:.4f} {DX:.4f} {fit.name}\n\n"
            f"#waveform: gaussiandot 1 7e9 pulse\n"
            f"#hertzian_dipole: z {SRC[0]:.4f} {SRC[1]:.4f} 0 pulse\n"
            f"#rx: {SRC[0]+R1:.4f} {SRC[1]:.4f} 0\n"
            f"#rx: {SRC[0]+R2:.4f} {SRC[1]:.4f} 0\n")
    (out_dir / "prop_test.in").write_text(body)
    print(f"model written for {TISSUE}: {fit}")


def main(run_dir: str) -> int:
    with h5py.File(Path(run_dir) / "prop_test.out", "r") as h:
        dt = float(h.attrs["dt"])
        e1 = np.asarray(h["/rxs/rx1/Ez"][:], float)
        e2 = np.asarray(h["/rxs/rx2/Ez"][:], float)

    f = np.fft.rfftfreq(e1.size, dt)
    band = (f >= F_LO) & (f <= F_HI)
    fb = f[band]
    H = (np.fft.rfft(e2) / np.fft.rfft(e1))[band]

    mat = T.get(TISSUE)
    k = 2 * np.pi * fb * np.sqrt(mat.eps_complex(fb)) / C0
    Ht = hankel2(0, k * R2) / hankel2(0, k * R1)

    mag_err = np.abs(np.abs(H) - np.abs(Ht)) / np.abs(Ht)
    ph_err = np.abs(np.angle(H * np.conj(Ht)))

    print(f"\n{TISSUE}: r1={R1*1e3:g} mm, r2={R2*1e3:g} mm, "
          f"{fb.size} bins over {F_LO/1e9:g}-{F_HI/1e9:g} GHz")
    print(f"(reference: Cole-Cole via the exact 2D Green's function)\n")
    print(f"{'f (GHz)':>9}{'|H| sim':>11}{'|H| thy':>11}{'err':>8}"
          f"{'dphase':>10}{'err (rad)':>11}")
    for fq in (3, 5, 7, 9, 11):
        i = int(np.argmin(np.abs(fb - fq * 1e9)))
        print(f"{fb[i]/1e9:9.2f}{np.abs(H[i]):11.5f}{np.abs(Ht[i]):11.5f}"
              f"{mag_err[i]:8.2%}{np.angle(H[i]):10.3f}{ph_err[i]:11.4f}")

    print(f"\nmagnitude: max {mag_err.max():.2%}, median {np.median(mag_err):.2%}")
    print(f"phase    : max {ph_err.max():.4f} rad, "
          f"median {np.median(ph_err):.4f} rad")

    ok = mag_err.max() < 0.10 and ph_err.max() < 0.15
    print("\nSTAGE 1 FDTD MATERIAL PASS" if ok
          else "\nSTAGE 1 FDTD MATERIAL FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--write":
        target = (Path(sys.argv[2]) if len(sys.argv) > 2
                  else Path(__file__).resolve().parent.parent / "config")
        target.mkdir(parents=True, exist_ok=True)
        write_models(target)
        sys.exit(0)
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
