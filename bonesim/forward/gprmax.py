"""gprMax FDTD backend: the forward model that produces results.

Emits gprMax input decks from a Phantom, drives the B-scan, and parses the
output back into the same ScanData the analytic model produces, so the
processing chain is unchanged.

Coordinates. The phantom uses x along the bone axis and z increasing into the
limb. gprMax 2D (TMz) uses x and y with y increasing upward, so depth maps as

    y = y_skin - z

with the antenna above the skin at y_skin + standoff.

Normalisation. A VNA reports S11 referenced to its calibration plane. The
simulation equivalent is to divide the recorded field by the same measurement
made with nothing present:

    S11(f, x_n) = FFT(E_total(t, x_n)) / FFT(E_incident(t))

E_incident is the free-space response of the co-located source and receiver. It
does not depend on scan position, so one reference run serves a whole B-scan.
Dividing by it removes the source spectrum and the near-field coupling of the
dipole, leaving a dimensionless reflection coefficient. Empty-scene subtraction
in the pipeline then yields the scattered-field ratio directly.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .base import ScanData

C0 = 299_792_458.0


@dataclass(frozen=True)
class GridSpec:
    """Discretisation and domain extent, in metres."""
    dx: float = 0.0002          # 0.2 mm: resolves a 0.3 mm kerf
    length: float = 0.100       # along the bone axis
    depth: float = 0.055        # total, including standoff and margins
    margin: float = 0.006       # clearance between PML and anything of interest
    time_window: float = 2.5e-9
    centre_freq: float = 7e9    # gaussiandot; -3.8/-2.5 dB at 3/11 GHz

    @property
    def dt(self) -> float:
        """2D Courant limit, which is what gprMax will choose."""
        return self.dx / (C0 * np.sqrt(2))

    def y_antenna(self) -> float:
        return self.depth - self.margin

    def y_skin(self, phantom) -> float:
        return self.y_antenna() - phantom.standoff

    def check(self, phantom) -> None:
        """Fail loudly rather than silently truncating the anatomy."""
        deepest = (self.y_skin(phantom)
                   - (phantom.z_far_cortex + phantom.cortex))
        if deepest < self.margin:
            raise ValueError(
                f"domain too shallow: anatomy reaches y={deepest*1e3:.1f} mm, "
                f"needs {self.margin*1e3:.1f} mm of margin. Raise depth.")
        t_needed = 2 * (phantom.standoff / C0
                        + (phantom.z_far_cortex + phantom.cortex)
                        * np.sqrt(45.0) / C0) + 4 / self.centre_freq
        if self.time_window < t_needed:
            raise ValueError(
                f"time window {self.time_window*1e9:.2f} ns is shorter than "
                f"the {t_needed*1e9:.2f} ns round trip to the far cortex")


def _materials_block(materials_file) -> str:
    text = Path(materials_file).read_text()
    if "#add_dispersion_debye" not in text:
        raise ValueError(f"{materials_file} has no Debye cards; "
                         f"run scripts/fit_debye_materials.py first")
    return text.strip()


def build_geometry(phantom, grid: GridSpec) -> str:
    """Layer boxes and the fracture, as gprMax commands."""
    grid.check(phantom)
    y_skin = grid.y_skin(phantom)
    lines = []

    def box(mat, z0, z1, x0=0.0, x1=None):
        x1 = grid.length if x1 is None else x1
        y0, y1 = y_skin - z1, y_skin - z0
        return (f"#box: {x0:.4f} {max(y0, 0.0):.4f} 0 "
                f"{x1:.4f} {y1:.4f} {grid.dx:.4f} {mat}")

    for mat, z0, z1 in phantom.stack():
        lines.append(box(mat, z0, z1))

    fr = phantom.fracture
    if fr is not None:
        # Written after the layers so the gap overwrites the cortex.
        z_end = phantom.z_cortex + fr.depth_fraction * phantom.cortex
        if abs(fr.angle_deg) < 1e-9:
            lines.append(box(fr.fill, phantom.z_cortex, z_end,
                             fr.x - fr.kerf / 2, fr.x + fr.kerf / 2))
        else:
            # An oblique cut, approximated by stacked offset slabs.
            n = max(4, int(np.ceil((z_end - phantom.z_cortex) / grid.dx)))
            edges = np.linspace(phantom.z_cortex, z_end, n + 1)
            tan = np.tan(np.radians(fr.angle_deg))
            for za, zb in zip(edges[:-1], edges[1:]):
                shift = (0.5 * (za + zb) - phantom.z_cortex) * tan
                lines.append(box(fr.fill, za, zb,
                                 fr.x + shift - fr.kerf / 2,
                                 fr.x + shift + fr.kerf / 2))
    return "\n".join(lines)


def build_input(phantom, grid: GridSpec, materials, x_start: float,
                n_positions: int, step: float, title: str = "") -> str:
    """One gprMax deck. Pass phantom=None for the free-space reference."""
    y_ant = grid.y_antenna()
    head = [
        f"#title: {title or 'bonesim B-scan'}",
        "##",
        "## Generated by bonesim/forward/gprmax.py - do not edit by hand.",
        "",
        f"#domain: {grid.length:.4f} {grid.depth:.4f} {grid.dx:.4f}",
        f"#dx_dy_dz: {grid.dx:.4f} {grid.dx:.4f} {grid.dx:.4f}",
        f"#time_window: {grid.time_window:g}",
        "",
        f"#waveform: gaussiandot 1 {grid.centre_freq:g} pulse",
        f"#hertzian_dipole: z {x_start:.4f} {y_ant:.4f} 0 pulse",
        f"#rx: {x_start:.4f} {y_ant:.4f} 0",
    ]
    if n_positions > 1:
        head += [f"#src_steps: {step:.4f} 0 0", f"#rx_steps: {step:.4f} 0 0"]
    if phantom is None:
        return "\n".join(head) + "\n"
    return ("\n".join(head) + "\n\n" + _materials_block(materials) + "\n\n"
            + build_geometry(phantom, grid) + "\n")


def read_trace(path):
    import h5py
    with h5py.File(path, "r") as h:
        return np.asarray(h["/rxs/rx1/Ez"][:], float), float(h.attrs["dt"])


def sorted_outputs(work, stem: str) -> list:
    """gprMax writes <stem>1.out .. <stem>N.out; order them numerically."""
    files = list(Path(work).glob(f"{stem}*.out"))
    if not files:
        raise FileNotFoundError(f"no output matching {stem}*.out in {work}")

    def index(p):
        m = re.search(rf"{re.escape(stem)}(\d*)\.out$", p.name)
        return int(m.group(1)) if m and m.group(1) else 0

    return sorted(files, key=index)


def assemble(work, stems, reference_stem: str, f_out, x, z_antenna,
             meta=None) -> ScanData:
    """Combine per-position traces into calibrated S11 on the target grid."""
    work = Path(work)
    e_inc, dt = read_trace(sorted_outputs(work, reference_stem)[0])

    traces = []
    for stem in stems:
        for p in sorted_outputs(work, stem):
            tr, dt_i = read_trace(p)
            if abs(dt_i - dt) > 1e-18:
                raise ValueError(f"{p.name} has a different time step")
            traces.append(tr)
    if len(traces) != x.size:
        raise ValueError(f"got {len(traces)} traces for {x.size} positions")

    n = max(e_inc.size, max(t.size for t in traces))
    f_sim = np.fft.rfftfreq(n, dt)
    inc = np.fft.rfft(e_inc, n=n)
    tot = np.stack([np.fft.rfft(t, n=n) for t in traces], axis=1)

    # Guard the division: outside the excitation band the reference is ~0.
    band = (f_sim >= f_out[0] * 0.5) & (f_sim <= f_out[-1] * 1.5)
    keep = np.abs(inc) >= 1e-6 * np.abs(inc[band]).max()
    s_sim = tot[keep] / inc[keep, None]
    f_keep = f_sim[keep]

    s11 = np.empty((f_out.size, x.size), dtype=complex)
    for i in range(x.size):
        s11[:, i] = (np.interp(f_out, f_keep, s_sim[:, i].real)
                     + 1j * np.interp(f_out, f_keep, s_sim[:, i].imag))
    return ScanData(f_out, x, s11, z_antenna,
                    meta={"model": "gprmax", **(meta or {})})


def run_models(work, decks, threads: int = 4, wsl_distro="Ubuntu",
               conda_env: str = "bonesim", timeout: float = 7200) -> None:
    """Run gprMax decks concurrently.

    Four processes of four threads each, never one process across sixteen: the
    solver is memory-bandwidth-bound and process parallelism is 4.7x faster on
    this machine (docs/compute-budget.md).
    """
    posix = Path(work).as_posix()
    if wsl_distro and len(posix) > 2 and posix[1] == ":":
        posix = f"/mnt/{posix[0].lower()}{posix[2:]}"
    runs = " & ".join(f"python -m gprMax {stem}.in -n {n} > {stem}.log 2>&1"
                      for stem, n in decks)
    inner = "; ".join([
        "source ~/miniforge3/etc/profile.d/conda.sh",
        f"conda activate {conda_env}",
        f"cd {posix}",
        f"export OMP_NUM_THREADS={threads}",
        runs + " & wait",
    ])
    cmd = (["wsl", "-d", wsl_distro, "--", "bash", "-lc", inner]
           if wsl_distro else ["bash", "-lc", inner])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(
            f"gprMax failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
