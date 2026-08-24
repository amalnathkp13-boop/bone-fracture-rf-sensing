"""openEMS model of the antipodal Vivaldi.

Proposal 2.3 asks for the antenna to be simulated before it is etched, and names
openEMS as the free tool adequate for S11 and near-field checks. It also makes a
specific claim worth testing rather than accepting:

    "FR4 (eps_r 4.4, tan_d 0.02) is acceptable up to about 8 GHz and will cost
    you a few dB above that. Rogers RO4350B (eps_r 3.48, tan_d 0.0037) is
    markedly better across the full band. If your budget allows one premium
    item, make it this."

Running both substrates through the same model turns that from advice into
evidence, and either confirms the recommendation or shows the cheaper board is
good enough - which is worth knowing when the whole build is INR 24k.

Kept separate from vivaldi.py so the geometry can be unit-tested without a
solver present.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from .vivaldi import Vivaldi

EPS0 = 8.8541878128e-12
C0 = 299_792_458.0


def _kappa(eps_r: float, tan_d: float, f_ref: float) -> float:
    """Equivalent conductivity for a dielectric loss tangent at f_ref.

    openEMS takes a conductivity, not a loss tangent, so the loss is matched at
    one frequency. Referenced at band centre, which slightly under-represents
    loss at 11 GHz and over-represents it at 3 GHz.
    """
    return 2 * np.pi * f_ref * EPS0 * eps_r * tan_d


def build(ant: Vivaldi, f0: float = 7e9, fc: float = 5e9,
          air: float = 30.0, max_res_air: float = 1.2,
          max_res_sub: float = 0.7, n_taper: int = 60,
          end_criteria: float = 1e-4, max_timesteps: int = 60000,
          nf2ff_freqs=None, boundary: str = "PML_8",
          sub_cells: int = 6):
    """Assemble the FDTD problem. Returns (FDTD, CSX, port, nf2ff).

    air, max_res_* are in millimetres, matching the mesh unit.

    nf2ff_freqs must be given if far-field patterns are wanted, and it matters
    a great deal. Without it the NF2FF box records the *time domain* field on
    all six surfaces at every timestep, which for this mesh is about 1.8 GB of
    HDF5 per run. Passing an explicit frequency list switches the box to
    frequency-domain accumulation - one complex field per surface per frequency
    - which is smaller by orders of magnitude and much faster, at the cost of
    fixing the pattern frequencies before the solve rather than after.

    Pass None to skip the far-field box entirely when only S11 is needed.
    """
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    fdtd = openEMS(NrTS=max_timesteps, EndCriteria=end_criteria)
    fdtd.SetGaussExcite(f0, fc)
    # PML_8, and `air` at least a quarter wavelength at the LOWEST frequency.
    #
    # The first version used MUR with 20 mm of air, which is 0.2 wavelengths at
    # 3 GHz - well inside the near field. Energy then failed to leave the
    # domain: every run hit the 60000-timestep ceiling with the residual energy
    # stuck at -37.9 dB instead of decaying to the -40 dB end criterion, and
    # the antenna behaved as a resonator, matching over about 1 GHz at
    # L/lambda_g of roughly 4.5 to 5.1 - a standing wave along the taper.
    fdtd.SetBoundaryCond([boundary] * 6)

    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    mesh = csx.GetGrid()
    mesh.SetDeltaUnit(1e-3)                       # millimetres

    h = ant.height
    sub = ant.sub

    # --- substrate -------------------------------------------------------
    kappa = _kappa(sub["eps_r"], sub["tan_d"], f0)
    dielectric = csx.AddMaterial("substrate", epsilon=sub["eps_r"],
                                 kappa=kappa)
    dielectric.AddBox([0, -ant.sub_width / 2, 0],
                      [ant.length, ant.sub_width / 2, h], priority=1)

    # --- the two arms ----------------------------------------------------
    upper = ant.upper_arm(n_taper)
    lower = ant.lower_arm(n_taper)
    top = csx.AddMetal("arm_top")
    top.AddPolygon(upper.T.tolist(), 2, h, priority=10)
    bot = csx.AddMetal("arm_bottom")
    bot.AddPolygon(lower.T.tolist(), 2, 0.0, priority=10)

    hw = ant.w_port / 2

    # --- feed ------------------------------------------------------------
    # A lumped port across the substrate at x = 0, between the overlapping
    # arms. That overlap is a parallel-strip line, which is why the antipodal
    # form needs no separate balun.
    # Extending the strips behind the port into the PML was tried and is a
    # trap: PEC inside a PML never lets the energy decay, and a single run went
    # from 45 s to over ten minutes without converging.
    port = fdtd.AddLumpedPort(
        1, 50, [0, -hw, 0], [0, hw, h],
        "z", 1.0, priority=5, edges2grid="xy")

    # --- mesh ------------------------------------------------------------
    # Substrate faces and the feed must land exactly on mesh lines; the taper
    # is sampled so the flare edge is not stepped too coarsely.
    x_lines = [-air, 0.0, ant.taper_start, ant.length, ant.length + air]
    x_lines += list(np.linspace(ant.taper_start, ant.length, 12))
    y_lines = [-ant.sub_width / 2 - air, -ant.sub_width / 2,
               -ant.feed_width / 2, -ant.w_port / 2, 0.0,
               ant.w_port / 2, ant.feed_width / 2,
               ant.sub_width / 2, ant.sub_width / 2 + air]
    y_lines += list(np.linspace(-ant.aperture / 2, ant.aperture / 2, 9))
    # The port integrates E across the substrate and H around the strip, so it
    # needs several cells through the thickness, not the bare minimum of three.
    z_lines = [-air] + list(np.linspace(0.0, h, sub_cells + 1)) + [h + air]
    # Refine in-plane around the port as well, for the same reason.
    x_lines += list(np.linspace(0.0, 3.0, 4))
    y_lines += list(np.linspace(-ant.feed_width, ant.feed_width, 9))

    mesh.AddLine("x", x_lines)
    mesh.AddLine("y", y_lines)
    mesh.AddLine("z", z_lines)
    mesh.SmoothMeshLines("x", max_res_air)
    mesh.SmoothMeshLines("y", max_res_air)
    mesh.SmoothMeshLines("z", max_res_air)

    nf2ff = None
    if nf2ff_freqs is not None:
        nf2ff = fdtd.CreateNF2FFBox(frequency=list(np.atleast_1d(nf2ff_freqs)))
    return fdtd, csx, port, nf2ff


def run(ant: Vivaldi, sim_path, freq: np.ndarray, verbose: int = 0,
        threads: int = 0, **build_kw):
    """Simulate and return a dict of S11 and the far-field handle.

    sim_path should be on a Linux-native filesystem. openEMS writes its field
    dumps there, and under WSL a path on /mnt/c is roughly an order of
    magnitude slower for this kind of I/O.

    threads=0 lets openEMS choose. The FDTD solver here is memory-bandwidth
    bound in the same way gprMax is, so there is little to gain past a few
    threads.
    """
    sim_path = Path(sim_path)
    sim_path.mkdir(parents=True, exist_ok=True)

    fdtd, csx, port, nf2ff = build(ant, **build_kw)
    fdtd.Run(str(sim_path), verbose=verbose, cleanup=True,
             numThreads=threads)

    port.CalcPort(str(sim_path), freq)
    s11 = port.uf_ref / port.uf_inc
    z_in = port.uf_tot / port.if_tot

    return {"f": freq, "s11": s11, "z_in": z_in,
            "antenna": ant, "sim_path": sim_path,
            "_nf2ff": nf2ff}


def pattern(result: dict, f_probe: float, theta=None, phi=(0.0, 90.0)):
    """Far-field cut at one frequency. Returns (theta, gain_dBi, Dmax_dBi)."""
    theta = np.arange(-180.0, 180.5, 2.0) if theta is None else theta
    nf = result["_nf2ff"].CalcNF2FF(
        str(result["sim_path"]), f_probe, theta, np.asarray(phi, float))
    e_norm = nf.E_norm[0]
    d_max = float(nf.Dmax[0])
    gain = 20 * np.log10(np.abs(e_norm[:, 0]) / np.abs(e_norm).max() + 1e-12)
    return theta, gain + 10 * np.log10(d_max), 10 * np.log10(d_max)


def bandwidth(freq: np.ndarray, s11: np.ndarray, level_db: float = -10.0):
    """Widest contiguous band where |S11| stays below level. (lo, hi, db).

    Reported as a contiguous run rather than as "fraction of points below
    -10 dB", because a scattered set of matched points is not a usable
    bandwidth.

    Widest rather than deepest: keying on the global minimum lets an isolated
    narrow resonance outside the operating band win, reporting a bandwidth of
    essentially zero at the wrong frequency. A tapered-slot antenna is meant to
    be matched over an octave and more, so extent is what matters, not depth.
    """
    db = 20 * np.log10(np.abs(s11) + 1e-30)
    good = db <= level_db
    if not good.any():
        return None, None, db

    best_lo = best_hi = None
    best_len = 0
    i = 0
    while i < good.size:
        if not good[i]:
            i += 1
            continue
        j = i
        while j + 1 < good.size and good[j + 1]:
            j += 1
        if j - i + 1 > best_len:
            best_len, best_lo, best_hi = j - i + 1, i, j
        i = j + 1
    return float(freq[best_lo]), float(freq[best_hi]), db
